# API Reference

## skill.py Entry Point

```python
def main(config_path: str, openclaw_client):
    """
    Entry point called by OpenClaw gateway.

    Args:
        config_path: Path to YAML configuration file
        openclaw_client: OpenClaw gateway client (for sending messages, etc.)
    """
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `email.credentials_file` | string | `~/.openclaw/email-assistant/credentials.json` | Gmail OAuth credentials |
| `email.token_file` | string | `~/.openclaw/email-assistant/token.json` | OAuth token storage |
| `email.monitor_email` | string | *required* | Email address to monitor |
| `features.strip_thinking` | bool | `true` | Remove AI reasoning markers from replies |
| `features.chinese_nl_parser` | bool | `true` | Enable Chinese date parsing |
| `features.default_meeting_duration` | int | `30` | Default meeting length (minutes) |
| `calendar.calendar_id` | string | `primary` | Calendar to create events in |
| `calendar.always_invite` | list[str] | `[]` | Additional attendees for every meeting |
| `logging.level` | string | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

## Events & Actions

The skill currently supports:

- **Incoming email** → Process and optionally reply
- **Meeting scheduling** → Create Google Calendar event with Meet link
- **Bounce detection** → Skip and mark as read

## Error Handling

Errors are logged to the configured log file. The skill continues running after errors (best effort).

## Future API

Planned extensions:
- Webhook triggers from other skills
- Manual email send API
- Status reporting endpoint
