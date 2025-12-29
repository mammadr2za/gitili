import subprocess
import requests
import sys

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/gitili/commit-message"

def get_git_diff():
    result = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True,
        text=True
    )
    if not result.stdout.strip():
        print("No staged changes. Run: git add .")
        sys.exit(1)
    return result.stdout

def get_commit_suggestions(diff_text):
    response = requests.get(
        N8N_WEBHOOK_URL,
        json={"diff": diff_text},
        timeout=60
    )
    response.raise_for_status()
    return response.json()["messages"]

def choose_message(messages):
    print("\nSuggested commit messages:\n")
    for i, msg in enumerate(messages, start=1):
        print(f"{i}. {msg}")

    choice = int(input("\nChoose (1-5): "))
    if choice < 1 or choice > 5:
        print("Invalid choice")
        sys.exit(1)

    return messages[choice - 1]

def commit(message):
    subprocess.run(["git", "commit", "-m", message])

def main():
    diff = get_git_diff()
    messages = get_commit_suggestions(diff)
    selected = choose_message(messages)
    commit(selected)

if __name__ == "__main__":
    main()
