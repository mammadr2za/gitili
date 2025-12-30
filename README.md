# Gitili

Gitili is a small CLI tool that:
- Suggests up to **5 Conventional Commits** messages from your staged `git diff`
- Lets you pick one and runs `git commit -m "..."`
- Optionally runs `git push` and sends a **Telegram notification** via **n8n**

> Gitili does NOT require Telegram to generate commit messages.
> Telegram is only needed for push notifications.

---

## Requirements

- Python 3.8+
- Git
- n8n running (local or server)
- For push notifications: Telegram bot token (BotFather) + n8n Telegram credentials

---

## Install

### Option 1: Install from source (recommended for development)
Clone the repo and install in editable mode:

```bash
git clone <YOUR_REPO_URL>
cd gitili
pip install -e .
# gitili
## Config (Required)

Gitili reads config from a file in the **project root**:

- `./config.json` (real config used by gitili)
- `./config.example.json` (example only)

### Setup

1) Copy example to config:

```bash
cp config.example.json config.json
