# Setup Guide

This guide walks you through setting up the OpenClaw Email Assistant.

## Prerequisites

- Python 3.10 or higher
- OpenClaw gateway running (http://localhost:8080)
- A Gmail account for the bot
- Google Cloud Console project with Gmail API enabled

## Step 1: Google Cloud OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Gmail API** and **Google Calendar API**
4. Go to **APIs & Services > Credentials**
5. Create **OAuth 2.0 Client ID** (Desktop app)
6. Download the credentials JSON file
7. Rename it to `credentials.json` and place in:
   ```
   ~/.openclaw/email-assistant/credentials.json
   ```

## Step 2: Install Dependencies

```bash
cd /path/to/openclaw-email-assistant
pip install -r requirements.txt
```

## Step 3: Configure

1. Copy the default config:
   ```bash
   cp config/default.yaml config/local.yaml
   ```

2. Edit `config/local.yaml`:
   - Set your monitor email
   - Set `OPENCLAW_API_KEY` environment variable or put it in the config
   - Adjust other settings as needed

3. Set environment variables:
   ```bash
   export OPENCLAW_API_KEY="your-openclaw-api-key"
   ```

## Step 4: First Run (OAuth Authorization)

The first time you run the skill, it will open a browser window for OAuth consent:

```bash
python skill.py config/local.yaml
```

Follow the prompts to authorize Gmail and Calendar access.

## Step 5: Integrate with OpenClaw

Add to your `openclaw.json`:

```json
{
  "skills": {
    "email-assistant": {
      "module": "path/to/openclaw-email-assistant/skill.py",
      "config": "path/to/openclaw-email-assistant/config/local.yaml"
    }
  }
}
```

Restart OpenClaw gateway:
```bash
openclaw gateway restart
```

## Testing

Send an email to your bot account with:
- "Schedule a meeting for tomorrow 3pm with test@example.com"
- Or any Chinese time expression: "下周二上午10点开会"

## Troubleshooting

- **OAuth errors**: Delete `token.json` and re-run to re-authorize
- **Permission denied**: Ensure Gmail API is enabled and OAuth client is correct
- **No emails received**: Check that the bot email is accessible and IMAP is enabled
- **Skill not loading**: Check OpenClaw logs for config syntax errors

See logs at: `~/.openclaw/logs/email-assistant.log`
