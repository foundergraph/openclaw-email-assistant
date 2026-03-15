# Architecture

## Overview

The OpenClaw Email Assistant is an OpenClaw skill that processes incoming emails, extracts actionable intents (primarily meeting scheduling), and performs automated actions using Gmail and Google Calendar APIs.

## Components

```
openclaw-email-assistant/
├── skill.py                 # Entry point for OpenClaw
├── src/
│   ├── email_bridge.py     # Core email processing loop
│   ├── nlu_parser.py       # Natural language understanding for dates
│   ├── bounce_detector.py  # Bounce detection logic
│   └── utils.py            # Helper functions
├── config/
│   ├── default.yaml        # Default configuration
│   └── schema.json         # Config validation schema
└── templates/
    └── email_templates.jinja2  # Response email templates
```

## Data Flow

1. **OpenClaw Gateway** loads the skill via `skill.py:main()`
2. **EmailBridge** initializes with config and OpenClaw client
3. **Polling Loop** (configurable interval):
   - Connect to Gmail API
   - Fetch unread messages (excluding bounces)
   - Parse email content
   - Determine intent (meeting_scheduling, question, unknown)
   - Execute action (create calendar event, send reply)
   - Mark processed emails as read
4. **Calendar Integration**: Use Google Calendar API to create events with Meet links
5. **Response Generation**: Use Jinja2 templates to compose replies

## Extensibility

- Add new intents in `email_bridge.py` → `_process_email()`
- Add new NL parsing in `nlu_parser.py`
- Customize email templates in `templates/`
- Add new configuration options in `config/schema.json`

## Security Considerations

- OAuth tokens stored in `token.json` (auto-refreshed)
- No email bodies logged by default
- Credentials never committed to git
- Skill runs with user's Gmail permissions only

## Configuration

See `config/default.yaml` for all options. Environment variable substitution is supported (`${VAR_NAME}`).

## Testing

Unit tests in `tests/`:
- `test_parser.py`: NL date parsing
- `test_bounce.py`: Bounce detection

Run with pytest.
