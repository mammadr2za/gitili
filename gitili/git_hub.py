import os
import sys
import requests

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("GITHUB_TOKEN not set")
    sys.exit(1)


def gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def list_repos():
    r = requests.get(
        f"{GITHUB_API}/user/repos",
        headers=gh_headers(),
        timeout=30
    )
    r.raise_for_status()

    return [
        {
            "name": repo["name"],
            "full_name": repo["full_name"]
        }
        for repo in r.json()
    ]


def list_branches(repo_full_name: str):
    owner, repo = repo_full_name.split("/", 1)

    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/branches",
        headers=gh_headers(),
        timeout=30
    )
    r.raise_for_status()

    return [b["name"] for b in r.json()]
