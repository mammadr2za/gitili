import argparse
import getpass
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

import requests


# ---------------- CONFIG ----------------

def load_config() -> Dict[str, Any]:
    cfg_path = Path.cwd() / "config.json"

    if not cfg_path.exists():
        print("Missing config.json in current directory.")
        print("Create it from config.example.json:")
        print("  cp config.example.json config.json")
        sys.exit(1)

    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read config.json: {e}")
        sys.exit(1)

    if not isinstance(data, dict):
        print("config.json must be a JSON object.")
        sys.exit(1)

    for key in ("commit_url", "push_url"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            print(f"config.json missing or invalid '{key}'")
            sys.exit(1)

    if "remote" in data:
        if not isinstance(data["remote"], str) or not data["remote"].strip():
            print("config.json invalid 'remote'")
            sys.exit(1)

    return data


# ---------------- GIT HELPERS ----------------

def run_git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True
    )


def git_out(*args, default: str = "") -> str:
    p = run_git(*args)
    if p.returncode != 0:
        return default
    return (p.stdout or "").strip() or default


def parse_repo_slug(remote_url: str) -> str:
    url = (remote_url or "").strip()
    if not url:
        return "unknown"

    if url.startswith("git@") and ":" in url:
        part = url.split(":", 1)[1]
    elif "://" in url:
        part = url.split("://", 1)[1]
        part = part.split("/", 1)[1] if "/" in part else part
    else:
        part = url

    if part.endswith(".git"):
        part = part[:-4]

    return part


# ---------------- COMMIT SUGGESTIONS ----------------

def get_staged_diff() -> str:
    p = run_git("diff", "--staged")

    if p.returncode != 0:
        print(p.stderr or "Failed to get staged diff")
        sys.exit(1)

    diff = (p.stdout or "").strip()

    if not diff:
        print("No staged changes. Run: git add .")
        sys.exit(1)

    return diff


def request_commit_suggestions(commit_url: str, diff_text: str) -> List[str]:
    r = requests.post(
        commit_url,
        json={"diff": diff_text},
        timeout=60
    )
    r.raise_for_status()

    data = r.json()

    if isinstance(data, list) and data:
        data = data[0]

    msgs = data.get("messages")

    if not isinstance(msgs, list) or not msgs:
        raise ValueError("Invalid response from n8n (missing messages array)")

    return msgs[:5]


def choose_message(messages: List[str]) -> str:
    print("\nSuggested commit messages:\n")

    for i, msg in enumerate(messages, start=1):
        print(f"{i}. {msg}")

    try:
        choice = int(input(f"\nChoose (1-{len(messages)}): ").strip())
    except ValueError:
        print("Invalid choice")
        sys.exit(1)

    if not (1 <= choice <= len(messages)):
        print("Invalid choice")
        sys.exit(1)

    return messages[choice - 1]


def do_commit(commit_url: str) -> int:
    diff = get_staged_diff()

    try:
        messages = request_commit_suggestions(commit_url, diff)
    except Exception as e:
        print(f"Failed to get commit suggestions: {e}")
        return 1

    selected = choose_message(messages)

    print(f"\nCommitting with:\n  {selected}\n")
    p = subprocess.run(["git", "commit", "-m", selected])
    return p.returncode


# ---------------- PUSH NOTIFY ----------------

def collect_push_info(remote_name: str) -> Dict[str, Any]:
    branch = git_out("rev-parse", "--abbrev-ref", "HEAD", default="unknown")
    user = getpass.getuser()

    remote_url = git_out("config", "--get", f"remote.{remote_name}.url", default="")
    repo_slug = parse_repo_slug(remote_url)

    upstream = git_out(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", default=""
    )

    to_sha = git_out("rev-parse", "HEAD", default="")
    from_sha = ""
    commits: List[str] = []
    files_changed = 0

    if upstream:
        from_sha = git_out("rev-parse", upstream, default="")

        log_txt = git_out(
            "log", "--oneline", f"{upstream}..HEAD", "-n", "10", default=""
        )
        if log_txt:
            commits = log_txt.splitlines()

        files_txt = git_out(
            "diff", "--name-only", f"{upstream}..HEAD", default=""
        )
        if files_txt:
            files_changed = len(
                [x for x in files_txt.splitlines() if x.strip()]
            )
    else:
        last_commit = git_out(
            "log", "-1", "--pretty=%h %s", default=""
        )
        if last_commit:
            commits = [last_commit]

    return {
        "user": user,
        "branch": branch,
        "remote_name": remote_name,
        "remote_url": remote_url or "unknown",
        "repo_slug": repo_slug,
        "from_sha": from_sha,
        "to_sha": to_sha,
        "commit_count": len(commits),
        "commits": commits,
        "files_changed": files_changed,
        "has_upstream": bool(upstream),
    }


def do_push(push_url: str, remote_name: str) -> int:
    info = collect_push_info(remote_name)

    if not info["has_upstream"]:
        p = subprocess.run(["git", "push", "-u", remote_name, info["branch"]])
    else:
        p = subprocess.run(["git", "push"])

    if p.returncode != 0:
        return p.returncode

    payload = {k: v for k, v in info.items() if k != "has_upstream"}

    try:
        r = requests.post(push_url, json=payload, timeout=30)
        r.raise_for_status()
        print("Push notification sent.")
    except Exception as e:
        print(f"Push succeeded, but notify failed: {e}")

    return 0


# ---------------- CLI ----------------

def main():
    cfg = load_config()

    commit_url = cfg["commit_url"].strip()
    push_url = cfg["push_url"].strip()
    default_remote = cfg.get("remote", "origin").strip()

    parser = argparse.ArgumentParser(
        prog="gitili",
        description="Commit message suggestions + push notifications via n8n / Telegram",
    )

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("commit", help="Suggest commit messages and run git commit")

    p_push = sub.add_parser("push", help="Run git push then notify Telegram")
    p_push.add_argument(
        "--remote",
        default=default_remote,
        help="Git remote name"
    )

    args = parser.parse_args()

    if args.cmd in (None, "commit"):
        sys.exit(do_commit(commit_url))

    if args.cmd == "push":
        sys.exit(do_push(push_url, args.remote))

    parser.print_help()


if __name__ == "__main__":
    main()
