#!/usr/bin/env python3
"""
OpenClaw Email Assistant — Core email processing bridge.
"""

import os
import json
import time
import logging
import datetime
import base64
import requests
from typing import Dict, Any, Optional, List

from .utils import decode_mime_header, extract_email_address, parse_email_address_list, extract_email_body, strip_thinking
from .bounce_detector import is_bounce_email
from .nlu_parser import EnglishDateParser

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # fallback

class EmailBridge:
    """
    Bridge between Gmail and OpenClaw.
    - Polls inbox for unread emails
    - Forwards to OpenClaw for intent classification
    - Executes actions (scheduling, task creation, replies)
    """

    def __init__(self, config_path: str, openclaw_client):
        """
        Initialize EmailBridge.

        Args:
            config_path: Path to YAML configuration file
            openclaw_client: OpenClaw gateway client (for API calls if needed)
        """
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.openclaw = openclaw_client
        self.logger = logging.getLogger(__name__)

        # Email config
        self.credentials_file = os.path.expanduser(self.config['email']['credentials_file'])
        self.token_file = os.path.expanduser(self.config['email']['token_file'])
        self.monitor_email = self.config['email']['monitor_email']

        # Feature flags
        self.strip_thinking = self.config['features'].get('strip_thinking', True)
        self.chinese_nl_parser = self.config['features'].get('chinese_nl_parser', False)  # Not used for now
        self.default_duration = self.config['features'].get('default_meeting_duration', 30)

        # Calendar config
        self.calendar_id = self.config['calendar'].get('calendar_id', 'primary')
        self.always_invite = self.config['calendar'].get('always_invite', [])

        # Logging config
        self._setup_logging()

        # State
        self.processed_emails = set()
        self.parser = EnglishDateParser(timezone="Asia/Shanghai")

        # Placeholder for Gmail/Calendar services (authenticate later)
        self.service = None
        self.calendar_service = None

        # Load processed emails history
        self._load_processed_emails()

    def _setup_logging(self):
        level = getattr(logging, self.config['logging'].get('level', 'INFO'))
        fmt = self.config['logging'].get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_file = os.path.expanduser(self.config['logging'].get('file', '~/.openclaw/logs/email-assistant.log'))

        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        logging.basicConfig(level=level, format=fmt, handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ])
        self.logger = logging.getLogger(__name__)

    def _load_processed_emails(self):
        """Load set of processed email IDs from disk."""
        processed_file = os.path.expanduser('~/.openclaw/email-assistant/processed_emails.json')
        try:
            if os.path.exists(processed_file):
                with open(processed_file, 'r') as f:
                    self.processed_emails = set(json.load(f))
        except Exception as e:
            self.logger.error(f"Failed to load processed emails: {e}")
            self.processed_emails = set()

    def _save_processed_emails(self):
        """Save processed email IDs to disk."""
        processed_file = os.path.expanduser('~/.openclaw/email-assistant/processed_emails.json')
        try:
            with open(processed_file, 'w') as f:
                json.dump(list(self.processed_emails), f)
        except Exception as e:
            self.logger.error(f"Failed to save processed emails: {e}")

    def authenticate(self):
        """Authenticate with Gmail and Calendar APIs using service account."""
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            self.logger.info(f"Authenticating as {self.monitor_email}")
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/gmail.modify']
            )
            delegated = credentials.with_subject(self.monitor_email)
            self.service = build('gmail', 'v1', credentials=delegated)
            self.logger.info("✅ Gmail authentication successful")

            # Calendar
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=['https://www.googleapis.com/auth/calendar.events']
            )
            delegated = credentials.with_subject(self.monitor_email)
            self.calendar_service = build('calendar', 'v3', credentials=delegated, cache_discovery=False)
            self.logger.info("✅ Calendar authentication successful")

        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {e}")
            raise

    def check_new_emails(self):
        """Poll Gmail for unread messages and process them."""
        self.logger.debug("🔍 check_new_emails invoked (polling)")
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=self.config.get('limits', {}).get('max_emails_per_run', 50)
            ).execute()
            messages = results.get('messages', [])
            self.logger.info(f"Gmail list returned {len(messages)} messages (estimate={results.get('resultSizeEstimate')})")

            for msg in messages:
                email_id = msg['id']
                if email_id in self.processed_emails:
                    continue

                email = self.service.users().messages().get(
                    userId='me',
                    id=email_id,
                    format='full'
                ).execute()

                email_data = self._extract_email_data(email)
                self.logger.debug(f"Extracted body (first 200 chars): {email_data['body'][:200]!r}")

                # Skip self-sent
                if email_data["from_email"].lower() == self.monitor_email.lower():
                    self.logger.info(f"⏭️ Skipping email from self: {email_data['subject']}")
                    self.processed_emails.add(email_id)
                    continue

                # Skip bounces
                if is_bounce_email(email_data["from_email"], email_data["subject"]):
                    self.logger.info(f"⏭️ Skipping bounce: {email_data['from_email']} - {email_data['subject']}")
                    self.processed_emails.add(email_id)
                    self._mark_as_read(email_id)
                    continue

                # Skip Google Calendar notifications (invitations, updates, cancellations)
                if self._is_calendar_notification(email_data):
                    self.logger.info(f"⏭️ Skipping calendar notification: {email_data['subject']} from {email_data['from_email']}")
                    self.processed_emails.add(email_id)
                    self._mark_as_read(email_id)
                    continue

                # Permission check (whitelist or mention)
                if not self._is_sender_allowed(email_data):
                    self.logger.info(f"⏭️ Skipping non-allowed sender: {email_data['from_email']}")
                    self.processed_emails.add(email_id)
                    continue

                # Process
                self.logger.info(f"📧 Processing email from: {email_data['from']} - Subject: {email_data['subject']}")
                self.logger.debug(f"Body (first 200 chars): {email_data['body'][:200]!r}")
                self._process_email(email_data)

                self.processed_emails.add(email_id)
                self._mark_as_read(email_id)

            if messages:
                self._save_processed_emails()

        except Exception as e:
            self.logger.error(f"Error checking emails: {e}")

    def _extract_email_data(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message into structured dict."""
        headers = email['payload']['headers']

        def get_header(name: str) -> str:
            val = next((h['value'] for h in headers if h['name'].lower() == name.lower()), '')
            return decode_mime_header(val)

        from_header = get_header('from')
        subject = get_header('subject')
        to_header = get_header('to')
        cc_header = get_header('cc')
        body = extract_email_body(email['payload'])

        sender_email = extract_email_address(from_header)
        recipient_emails = []
        recipient_headers = []
        if to_header:
            recipient_headers.append(('To', to_header))
            recipient_emails.extend(parse_email_address_list(to_header))
        if cc_header:
            recipient_headers.append(('Cc', cc_header))
            recipient_emails.extend(parse_email_address_list(cc_header))

        recipient_emails = [e for e in recipient_emails if e.lower() != sender_email.lower()]

        return {
            'id': email['id'],
            'from': from_header,
            'from_email': sender_email,
            'to': to_header,
            'cc': cc_header,
            'recipient_headers': recipient_headers,
            'recipient_emails': recipient_emails,
            'subject': subject,
            'body': body,
            'thread_id': email['threadId']
        }

    def _is_sender_allowed(self, email_data: Dict[str, Any]) -> bool:
        """Check if sender is whitelisted or mentioned in email body."""
        whitelist = self.config.get('whitelisted_senders', [])
        sender = email_data['from_email'].lower()
        if sender in [s.lower() for s in whitelist]:
            return True

        # Check for mention triggers (e.g., @jessie)
        body = email_data.get('body', '')
        triggers = self.config.get('mention_triggers', [])
        body_lower = body.lower()
        for trigger in triggers:
            if trigger.lower() in body_lower:
                return True
        return False

    def _is_calendar_notification(self, email_data: Dict[str, Any]) -> bool:
        """Detect if this email is a Google Calendar invitation/update/cancellation."""
        sender = email_data['from_email'].lower()
        # Known Google Calendar notification senders
        calendar_senders = [
            'calendar-notification@google.com',
            'invitation@google.com',
            'noreply@google.com',
        ]
        for cs in calendar_senders:
            if cs in sender:
                return True

        # Check for X-Calendar-Event or X-Google-Original-From headers
        headers = email_data.get('headers', [])
        for hdr in headers:
            if isinstance(hdr, dict):
                name = hdr.get('name', '').lower()
                if name in ('x-calendar-event', 'x-google-original-from'):
                    return True

        # Check body for iCalendar data
        body = email_data.get('body', '')
        if 'BEGIN:VCALENDAR' in body or 'END:VCALENDAR' in body:
            return True
        if ' METHOD:' in body and 'UID:' in body:
            return True

        return False

    def _mark_as_read(self, message_id: str):
        """Remove UNREAD label from Gmail message."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as e:
            self.logger.error(f"Failed to mark as read: {e}")

    def _process_email(self, email_data: Dict[str, Any]):
        """
        Send email to OpenClaw for intent classification and action.
        Then send reply if needed.
        """
        try:
            sender = email_data['from_email']
            subject = email_data['subject']
            body = email_data['body'].strip()
            recipients = ', '.join(email_data.get('recipient_emails', []))
            email_context = (
                f"Subject: {subject}\n"
                f"From: {sender}\n"
                f"To: {recipients}\n\n"
                f"{body}"
            )

            # Build tools for OpenClaw
            tools = [
                {"type": "function", "function": {"name": "schedule_meeting", "description": "Schedule a Google Calendar meeting", "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "Full email content"}}, "required": ["text"]}}},
                {"type": "function", "function": {"name": "create_notion_task", "description": "Create a Notion task", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}
            ]

            # Build OpenClaw API request
            agent_id = self.config.get('openclaw', {}).get('agent_id', 'email_assistant')
            payload = {
                "agentId": agent_id,
                "model": "openclaw",
                "thinking": "off",
                "messages": [
                    {"role": "system", "content": self.config.get('system_prompt', """You are Jessie, the Meeting Coordinator at FounderGraph AI. When writing an email reply, your output MUST contain ONLY the final email body. DO NOT include any analysis, reasoning, planning, or meta-commentary. Do not mention you are an AI or bot.

If the email is a meeting request, call schedule_meeting.
If it's a task request, call create_notion_task.
For other emails, write a short, friendly reply as Jessie.""" ) },
                    {"role": "user", "content": email_context}
                ],
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.1,
                "max_tokens": 300
            }

            # Add OpenClaw token if available
            headers = {"Content-Type": "application/json"}
            openclaw_token = self.config.get('openclaw', {}).get('api_key') or os.getenv('OPENCLAW_API_KEY')
            if openclaw_token:
                headers["Authorization"] = f"Bearer {openclaw_token}"

            gateway_url = self.config.get('openclaw', {}).get('gateway_url', 'http://localhost:8080')
            api_url = f"{gateway_url.rstrip('/')}/v1/chat/completions"

            self.logger.info("Calling OpenClaw to classify email...")
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=180)
                response.raise_for_status()
            except requests.exceptions.Timeout:
                self.logger.error("OpenClaw API timeout — will retry once")
                # Retry once after brief wait
                import time
                time.sleep(2)
                try:
                    response = requests.post(api_url, headers=headers, json=payload, timeout=180)
                    response.raise_for_status()
                except requests.exceptions.Timeout:
                    self.logger.error("OpenClaw API timeout on retry — giving up")
                    return
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"OpenClaw API error on retry: {e}")
                    return
            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenClaw API error: {e}")
                return

            res_json = response.json()
            message = res_json.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            message_content = message.get("content", "").strip()

            # Extract recipients from original email (To + Cc)
            recipient_emails = email_data.get('recipient_emails', [])

            reply = None
            if tool_calls:
                for call in tool_calls:
                    func_name = call.get("function", {}).get("name")
                    if func_name in ("schedule_meeting", "create_notion_task"):
                        args_str = call["function"]["arguments"]
                        try:
                            args = json.loads(args_str)
                            email_text = args.get("text", email_context)
                        except Exception as e:
                            self.logger.error(f"Failed to parse tool arguments: {e}")
                            break

                        if func_name == "schedule_meeting":
                            reply = self._handle_schedule_meeting(email_text, recipient_emails)
                        elif func_name == "create_notion_task":
                            reply = self._handle_create_notion_task(email_text, sender)
                        break

            if not reply and message_content:
                reply = message_content

            if reply:
                self._send_reply(sender, subject, reply, email_data['thread_id'])
            else:
                self.logger.warning("No reply generated")

        except Exception as e:
            self.logger.error(f"Error processing email: {e}")

    def _handle_schedule_meeting(self, email_text: str, recipients: list) -> Optional[str]:
        """
        Schedule a meeting based on email content.
        Uses google_meetings skill bundled in this repo.
        """
        try:
            # Import from local google_meetings package (relative to repo root)
            import sys
            import os
            # Get the repo root: this file is in src/, so parent is repo root
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from google_meetings.skill import schedule_meeting as gm_schedule_meeting

            # email_text contains headers + body. We also have recipients list.
            # The skill will extract the sender itself from the From header.
            result = gm_schedule_meeting(email_text, recipients=recipients)
            if result:
                return f"✅ Meeting scheduled: {result.get('start')} — {result.get('meet_link')}"
        except Exception as e:
            self.logger.warning(f"google_meetings skill not available: {e}")

        # Fallback: simple stub
        return self._schedule_meeting_stub(email_text, recipients)

    def _schedule_meeting_stub(self, email_text: str, recipients: list) -> Optional[str]:
        """Very basic meeting scheduling fallback."""
        if not self.calendar_service:
            self.logger.warning("Calendar service not available")
            return None
        try:
            from datetime import timedelta
            now = datetime.datetime.now(ZoneInfo("Asia/Shanghai"))
            start = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            end = start + timedelta(minutes=self.default_duration)

            # Use provided recipients (exclude sender duplicates and bot email)
            attendees = list(recipients) if recipients else []
            # Ensure unique and remove any empty
            attendees = list(set([e for e in attendees if e and '@' in e]))
            # Also always include the main address from config
            always_invite = self.config.get('calendar', {}).get('always_invite', [])
            for addr in always_invite:
                if addr not in attendees:
                    attendees.append(addr)

            event = {
                'summary': 'Meeting scheduled by Jessie',
                'description': f'Scheduled from email request',
                'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Shanghai'},
                'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Shanghai'},
                'attendees': [{'email': email} for email in attendees],
                'conferenceData': {'createRequest': {'requestId': f'meet-{int(time.time())}'}}
            }

            created = self.calendar_service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()

            meet_link = ''
            if 'conferenceData' in created:
                for ep in created['conferenceData'].get('entryPoints', []):
                    if ep.get('entryPointType') == 'video':
                        meet_link = ep['uri']
                        break

            return f"✅ Meeting scheduled: {start.strftime('%Y-%m-%d %H:%M')} — {meet_link or 'no Meet link'}"

        except Exception as e:
            self.logger.error(f"Failed to schedule meeting (stub): {e}")
            return None

    def _handle_create_notion_task(self, text: str, sender_email: str) -> Optional[str]:
        """Create a Notion task from email text."""
        try:
            from notion_client import Client
            notion_api_key = self.config.get('notion', {}).get('api_key') or os.getenv('NOTION_API_KEY')
            if not notion_api_key:
                self.logger.error("Notion API key not configured")
                return None

            notion = Client(auth=notion_api_key)
            database_id = self.config.get('notion', {}).get('tasks_database_id') or os.getenv('NOTION_TASKS_DATABASE_ID')
            if not database_id:
                self.logger.error("Notion tasks database ID not configured")
                return None

            title = text.strip()[:100]
            new_page = {
                "Name": {"title": [{"text": {"content": title}}]},
                "Priority": {"select": {"name": "Medium"}},
                "Notes": {"rich_text": [{"text": {"content": f"Created from email by {sender_email}"}}]}
            }
            notion.pages.create(parent={"database_id": database_id}, properties=new_page)
            return f"✅ Task created: {title}"

        except Exception as e:
            self.logger.error(f"Failed to create Notion task: {e}")
            return None

    def _send_reply(self, to_email: str, original_subject: str, reply_body: str, thread_id: str):
        """Send a reply email via Gmail."""
        try:
            if self.strip_thinking:
                reply_body = strip_thinking(reply_body)

            subject = f"Re: {original_subject}" if not original_subject.lower().startswith('re:') else original_subject

            headers = [
                f"To: {to_email}",
                f"Subject: {subject}",
                f"References: {thread_id}",
                f"In-Reply-To: {thread_id}"
            ]
            bcc = self.config.get('email', {}).get('bcc_email')
            if bcc:
                headers.append(f"Bcc: {bcc}")

            reply_text = (
                "\n".join(headers) + "\n\n" +
                f"{reply_body}\n\n" +
                f"--\nJessie\nMeeting Coordinator, FounderGraph AI"
            )

            raw_b64 = base64.urlsafe_b64encode(reply_text.encode('utf-8')).decode('utf-8')
            message = {'raw': raw_b64, 'threadId': thread_id}

            self.service.users().messages().send(userId='me', body=message).execute()
            self.logger.info(f"✅ Reply sent to {to_email}")

        except Exception as e:
            self.logger.error(f"Failed to send reply: {e}")

    def start(self):
        """Main loop: authenticate and poll continuously."""
        self.authenticate()
        self.logger.info(f"🤖 Email Assistant started — checking every {self.config.get('check_interval', 30)}s")
        while True:
            try:
                self.check_new_emails()
                time.sleep(self.config.get('check_interval', 30))
            except KeyboardInterrupt:
                self.logger.info("🛑 Shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(self.config.get('check_interval', 30))
