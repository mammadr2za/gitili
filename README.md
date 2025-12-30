## n8n Setup (Required)

Gitili needs n8n to:
1) generate 5 commit message suggestions
2) send Telegram notifications after `git push`

### 1) Import the n8n workflow

1. Open n8n in your browser
2. Create a new workflow (or open an empty one)
3. Click **Import** → **Import from Clipboard**
4. Paste the workflow JSON from this repository:

- `n8n/workflow.json` (recommended to include in this repo)
  - It contains two webhooks:
    - `/webhook/gitili/commit-message`
    - `/webhook/gitili/push`

5. Save the workflow
6. Configure credentials:
   - **OpenAI** credentials in the “Message a model” node
   - **Telegram** credentials in the “Telegram Send Message” node

7. Activate the workflow (toggle **Active**)

> IMPORTANT:
> - When the workflow is **Active**, n8n uses `/webhook/...`
> - When testing in “Listen/Test”, n8n uses `/webhook-test/...`

---

### 2) Create Telegram bot + credentials (for push notifications)

1. In Telegram, open `@BotFather`
2. Create a bot: `/newbot`
3. Copy the bot token
4. In n8n → **Credentials** → create **Telegram API** credential
5. Paste the bot token

To get your `chat_id`, send a message to your bot and run:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
## Run n8n (Docker) + Import Workflow

This repo includes an n8n workflow at:

- `n8n/workflow.json`

### 1) Start n8n with Docker

Requirements:
- Docker + Docker Compose installed

From the project root:

```bash
cp .env.example .env
# edit .env and set:
# - N8N_ENCRYPTION_KEY
# - (optional) basic auth user/pass
nano .env
