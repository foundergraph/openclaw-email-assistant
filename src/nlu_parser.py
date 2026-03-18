"""Natural Language Parser for meeting scheduling (English only for now)."""

import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Optional, Tuple

try:
    from dateutil import parser as dateutil_parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

class EnglishDateParser:
    """Parse English date/time expressions into datetime objects."""

    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.timezone = ZoneInfo(timezone)

    def parse(self, text: str, now: Optional[datetime] = None) -> Optional[Tuple[datetime, datetime]]:
        """
        Parse a meeting time expression and return (start, end) datetimes.
        Returns None if parsing fails or is too ambiguous.
        """
        if now is None:
            now = datetime.now(self.timezone)

        text_lower = text.lower().strip()

        # If dateutil is available, try it first with dayfirst=True
        if HAS_DATEUTIL:
            try:
                # Parse with fuzzy=True to ignore non-date words, dayfirst to prefer DD/MM
                dt = dateutil_parser.parse(text_lower, fuzzy=True, dayfirst=True, default=now)
                # Reject if year is far away (more than 2 years from now) -> ambiguous
                if abs((dt - now).days) > 730:
                    return None
                # Ensure timezone-aware in the configured tz
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=self.timezone)
                else:
                    dt = dt.astimezone(self.timezone)
                # If date part is today but time already passed, move to next day
                if dt.date() == now.date() and dt < now:
                    dt += timedelta(days=1)
                end = dt + timedelta(minutes=30)
                return dt, end
            except (ValueError, OverflowError):
                return None

        # Fallback: simple heuristic patterns
        # "tomorrow at 3pm"
        if 'tomorrow' in text_lower:
            hour, minute = self._extract_hour_minute(text_lower)
            if hour is not None:
                start = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=1)
                end = start + timedelta(minutes=30)
                return start, end

        # "next <weekday> at <time>"
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(weekdays):
            if f'next {day}' in text_lower or f'next {day}s' in text_lower:
                hour, minute = self._extract_hour_minute(text_lower)
                if hour is not None:
                    days_ahead = (i - now.weekday() + 7) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
                    end = start + timedelta(minutes=30)
                    return start, end

        # "today at <time>"
        if 'today' in text_lower:
            hour, minute = self._extract_hour_minute(text_lower)
            if hour is not None:
                start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if start < now:
                    start += timedelta(days=1)
                end = start + timedelta(minutes=30)
                return start, end

        # Simple time like "3pm" or "15:00"
        hour, minute = self._extract_hour_minute(text_lower)
        if hour is not None:
            start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if start < now:
                start += timedelta(days=1)
            end = start + timedelta(minutes=30)
            return start, end

        return None

    def _extract_hour_minute(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract hour and minute from text. Returns (hour, minute) or (None, None)."""
        # Match patterns like "3pm", "15:00", "3:30 pm", "15h30"
        patterns = [
            r'(\d{1,2})(?::|h|\.)?(\d{2})?\s*(am|pm)?',  # 3pm, 15:00, 3.30pm
            r'(\d{1,2})\s*(am|pm)',  # 3 pm
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                ampm = match.group(3)
                if ampm:
                    if ampm.lower() == 'pm' and hour < 12:
                        hour += 12
                    elif ampm.lower() == 'am' and hour == 12:
                        hour = 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return hour, minute
        return None, None
