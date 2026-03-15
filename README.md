# 🤖 OpenClaw Email Assistant

An AI-powered email bot built for [OpenClaw](https://openclaw.ai) that intelligently manages your inbox, schedules meetings from natural language (including Chinese), and handles bounce notifications automatically.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Compatible-green.svg)](https://openclaw.ai)

---

## ✨ Features

- **Smart Meeting Scheduling**: Parse date/time expressions in English and Chinese ("明天下午3点", "next Tuesday 10am", "tomorrow at 3pm") and auto-create Google Calendar events with Meet links
- **Bounce Handling**: Automatically detect and skip bounce notifications to prevent loops
- **Thinking Stripping**: Optional filter to remove AI reasoning markers from outgoing replies
- **OpenClaw Native**: Seamlessly integrates as an OpenClaw skill with standard interface
- **Extensible**: Easy to add custom filters, templates, and actions
- **Production-Ready**: Robust error handling, logging, and OAuth token refresh

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- OpenClaw gateway running (`openclaw gateway start`)
- Gmail API credentials (OAuth 2.0)

### Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/openclaw-email-assistant.git
   cd openclaw-email-assistant
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run setup script**
   ```bash
   ./scripts/setup.sh
   ```
   This will:
   - Check for credentials.json
   - Install dependencies
   - Create config/local.yaml

4. **Configure**
   Edit `config/local.yaml`:
   ```yaml
   email:
     monitor_email: "your-bot@example.com"
   openclaw:
     api_key: "${OPENCLAW_API_KEY}"  # Set env var
   ```

5. **Authorize Gmail access**
   First run opens browser for OAuth consent:
   ```bash
   python skill.py config/local.yaml
   ```

6. **Add to OpenClaw**
   In your `openclaw.json`:
   ```json
   {
     "skills": {
       "email-assistant": {
         "module": "/full/path/to/openclaw-email-assistant/skill.py",
         "config": "/full/path/to/openclaw-email-assistant/config/local.yaml"
       }
     }
   }
   ```

7. **Restart Gateway**
   ```bash
   openclaw gateway restart
   ```

That's it! The skill will now process incoming emails automatically.

---

## 📖 Documentation

- [Setup Guide](docs/SETUP.md) — Detailed OAuth setup and troubleshooting
- [Architecture](docs/ARCHITECTURE.md) — How it works under the hood
- [API Reference](docs/API.md) — Configuration options and extensibility

---

## 🔐 Security

- Uses OAuth 2.0 — no passwords stored
- Tokens auto-refresh; stored in `~/.openclaw/email-assistant/token.json`
- Credentials and tokens should **never** be committed to git
- Email bodies are not logged by default
- Scope limited to Gmail and Calendar for the configured bot account only

**Review the code before deploying.** You are responsible for your own email privacy and data handling.

---

## 🛠️ Development

### Project Structure

```
openclaw-email-assistant/
├── skill.py                 # OpenClaw entry point
├── src/
│   ├── email_bridge.py      # Core email processing
│   ├── nlu_parser.py        # Date/time NL parsing
│   ├── bounce_detector.py   # Bounce detection
│   └── utils.py             # Utilities
├── config/
│   ├── default.yaml
│   └── schema.json
├── docs/
├── templates/
├── tests/
├── scripts/
└── examples/
```

### Running Tests

```bash
pytest tests/
```

### Docker (Optional)

```bash
docker build -t openclaw-email-assistant .
docker-compose -f examples/docker-compose.yml up -d
```

---

## 📝 License

MIT © Your Name. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built for the OpenClaw community. Special thanks to the OpenClaw team for the amazing platform.

---

**Questions?** Open an issue or join the [OpenClaw Discord](https://discord.gg/clawd).
