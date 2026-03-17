# Google Meetings Scheduler Skill

Parse natural language meeting requests (in Chinese or English) and automatically schedule Google Calendar events with Google Meet links.

## Overview

This skill provides a single function `schedule_meeting(text: str) -> dict` that:

1. Extracts date/time from text like "tomorrow 3pm", "下周三上午10点", "March 15 2:30pm"
2. Extracts attendee email addresses from the text
3. Checks calendar for conflicts
4. Creates an event with a Google Meet link
5. Sends email invitations to all attendees

Timezone: Asia/Shanghai (configurable). Default duration: 30 minutes.

## Usage

```python
from google_meetings_skill import schedule_meeting

result = schedule_meeting("Can we meet tomorrow at 3pm with alice@example.com?")
# Returns dict with keys: id, summary, start, end, meetLink, htmlLink
```

The skill is already integrated into the Email Assistant (`email_bridge.py`). When a meeting request email arrives, the bot calls this skill and sends the confirmation as a reply.

## Configuration

The skill reads these environment variables (all optional):

- `GOOGLE_MEETINGS_SERVICE_ACCOUNT`: Path to service account JSON. Default: `/home/ubuntu/openclaw-email-bot/credentials.json`
- `GOOGLE_MEETINGS_USER_EMAIL`: The calendar owner email. Default: `jessie@foundergraphai.com`
- `GOOGLE_MEETINGS_TIMEZONE`: Timezone string. Default: `Asia/Shanghai`

The service account must have:
- Calendar API enabled
- Domain-wide delegation configured for the user email
- Scopes: `https://www.googleapis.com/auth/calendar.events`

## Supported Time Formats

Chinese:
- 今天下午3点, 明天上午10点半, 后天晚上7点
- 下周一/下周二/下周三/...
- 3月10日下午4点

English:
- tomorrow 3pm, next tuesday 10am, friday 2:30pm
- March 10 4pm, 2026-03-15 14:00

If no specific time is found, defaults to next available slot in the preferred period (morning/afternoon/evening) if indicated, otherwise 9:00 AM.

## Automatic Attendees

The Email Assistant automatically adds:
- `allen@foundergraphai.com` to every meeting
- Any recipient addresses from the email headers

Additional emails found in the email body are also included.

## Error Handling

Returns an error string if:
- Time cannot be parsed
- Calendar is unavailable
- Conflict found (returns a warning with conflict list)

The caller (`email_bridge.py`) will log errors and either fall back to a stub or skip scheduling.

## Logging

The skill uses Python's `logging` module at INFO level for major steps. Logs go to the root logger; ensure your application configures logging.

## Development

To test standalone:

```bash
GOOGLE_MEETINGS_USER_EMAIL=jessie@foundergraphai.com python3 skill.py
```

(Edit `skill.py` to change the test case at the bottom.)

## Files

- `skill.py` — main implementation
- `SKILL.md` — this documentation
- `skill.json` — OpenClaw skill manifest

## Notes

- The skill expects timezone-aware datetimes and handles conversions internally.
- Events are created with `conferenceData` to generate Google Meet links.
- All times in the event are set in the configured timezone.
