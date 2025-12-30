import argparse
import getpass
import os
import subprocess
import sys
from typing import List

import requests

DEFAULT_COMMIT_URL = "http://localhost:5678/webhook/gitili/commit-message"
DEFAULT_PUSH_URL = "http://localhost:5678/webhook/gitili/push"


def run_git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


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


# ---------------- Commit Suggestions ----------------

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
    r = requests.get(commit_url, json={"diff": diff_text}, timeout=60)
    r.raise_for_status()
    data = r.json()

    # Support both {messages:[...]} and [{messages:[...]}]
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
        print(f"Failed to get suggestions: {e}")
        return 1

    selected = choose_message(messages)

    print(f"\nCommitting with: {selected}\n")
    p = subprocess.run(["git", "commit", "-m", selected])
    return p.returncode


# ---------------- Push Notify ----------------

def collect_push_info(remote_name: str) -> dict:
    branch = git_out("rev-parse", "--abbrev-ref", "HEAD", default="unknown")
    user = getpass.getuser()

    remote_url = git_out("config", "--get", f"remote.{remote_name}.url", default="")
    repo_slug = parse_repo_slug(remote_url) if remote_url else "unknown"

    upstream = git_out("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", default="")
    to_sha = git_out("rev-parse", "HEAD", default="")
    from_sha = ""
    commits = []
    files_changed = 0

    if upstream:
        from_sha = git_out("rev-parse", upstream, default="")
        log_txt = git_out("log", "--oneline", f"{upstream}..HEAD", "-n", "10", default="")
        if log_txt:
            commits = log_txt.splitlines()

        files_txt = git_out("diff", "--name-only", f"{upstream}..HEAD", default="")
        if files_txt:
            files_changed = len([x for x in files_txt.splitlines() if x.strip()])
    else:
        # no upstream: just include last commit
        last_commit = git_out("log", "-1", "--pretty=%h %s", default="")
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

    # run push
    if not info["has_upstream"]:
        # first push, set upstream
        p = subprocess.run(["git", "push", "-u", remote_name, info["branch"]])
    else:
        p = subprocess.run(["git", "push"])

    if p.returncode != 0:
        return p.returncode

    # notify n8n -> Telegram
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
    parser = argparse.ArgumentParser(
        prog="gitili",
        description="Commit message suggestions + push notifications via n8n/Telegram",
    )

    parser.add_argument(
        "--commit-url",
        default=os.getenv("GITILI_COMMIT_URL", DEFAULT_COMMIT_URL),
        help="n8n webhook URL for commit suggestions",
    )
    parser.add_argument(
        "--push-url",
        default=os.getenv("GITILI_PUSH_URL", DEFAULT_PUSH_URL),
        help="n8n webhook URL for push notifications",
    )

    sub = parser.add_subparsers(dest="cmd")

    # Optional explicit commit command (default when no subcommand)
    sub.add_parser("commit", help="Suggest commit messages and run git commit")

    p_push = sub.add_parser("push", help="Run git push then notify Telegram via n8n")
    p_push.add_argument("--remote", default="origin", help="Git remote name (default: origin)")

    args = parser.parse_args()

    # Default behavior: `gitili` == commit flow
    if args.cmd in (None, "commit"):
        sys.exit(do_commit(args.commit_url))

    if args.cmd == "push":
        sys.exit(do_push(args.push_url, args.remote))

    parser.print_help()
    return 0


if __name__ == "__main__":
    main()
