#!/usr/bin/env python3
"""
Google Meetings Scheduler - 让 Jessie 自动安排 Google Calendar 会议
集成到主会话，通过自然语言指令创建事件
"""

import os
import re
import json
import logging
import requests
from email.utils import getaddresses
from datetime import datetime, timedelta, time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # fallback

logger = logging.getLogger(__name__)

# ============== 配置 ==============
SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_MEETINGS_SERVICE_ACCOUNT', '/home/ubuntu/.openclaw/email-assistant/credentials.json')
# 你的邮箱（日历所有者）
USER_EMAIL = "jessie@foundergraphai.com"
# 默认时长（分钟）
DEFAULT_DURATION = 30
# 用户时区（东八区 = UTC+8）
USER_TIMEZONE = os.getenv('GOOGLE_MEETINGS_TIMEZONE', 'Asia/Shanghai')
# Gmail sending (使用同一个 service account，需要启用 Gmail API 和 domain-wide delegation)
SEND_EMAIL = True  # 是否发送邀请邮件
# ==================================

# 英文星期映射
WEEKDAYS_CN = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
}

def generate_meeting_title(request_text: str, existing_summary: str = None) -> str:
    """
    Generate meeting title. For now, skip LLM and just clean up the existing summary.
    """
    if existing_summary and len(existing_summary.strip()) > 2 and existing_summary.lower() not in ('meeting', 'untitled'):
        # Basic cleanup: remove extra whitespace and any "with" leading fragments that are not titles
        title = existing_summary.strip()
        # If the summary starts with "with " (e.g., "with allen@..."), trim that part
        if title.lower().startswith('with '):
            # find the first email or non-email part after "with"
            remainder = title[5:].strip()
            # If remainder contains an email, take text before first email
            import re
            m = re.search(r'[\w\.-]+@[\w\.-]+', remainder)
            if m:
                title = remainder[:m.start()].strip()
            else:
                title = remainder
        # Ensure title is not empty after cleanup
        if title and len(title) >= 2:
            return title
    # Fallback
    return "Meeting"

def get_google_service(api_name='calendar', api_version='v3', scopes=None):
    """获取Google API服务对象"""
    if scopes is None:
        scopes = ['https://www.googleapis.com/auth/calendar.events']
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    delegated = credentials.with_subject(USER_EMAIL)
    return build(api_name, api_version, credentials=delegated, cache_discovery=False)

def parse_relative_date(text: str, base_date: datetime = None):
    """
    解析中文相对时间
    支持的格式：
    - "今天下午3点"
    - "明天上午10点半"
    - "下周二下午2点"
    - "3月10日下午4点"
    返回：timezone-aware datetime in USER_TIMEZONE

    Note: Minutes are rounded to nearest 15-minute increment to avoid odd times like :04 or :34.
    """
    if base_date is None:
        base_date = datetime.now(ZoneInfo(USER_TIMEZONE))

    # 标准化文本
    text = text.lower().strip()
    period_hint = None
    if '上午' in text or 'morning' in text:
        period_hint = 'morning'
    elif '下午' in text or 'afternoon' in text or 'pm' in text:
        period_hint = 'afternoon'
    elif '晚上' in text or 'evening' in text or 'night' in text:
        period_hint = 'evening'

    # 匹配 "今天/明天/后天/下X"
    day_offset = 0


    # English patterns (if no Chinese pattern matched)
    if day_offset == 0 and not any(kw in text for kw in ['今天', '明天', '后天', '下']):
        text_lower = text.lower()
        # Check for "tomorrow"
        if 'tomorrow' in text_lower:
            day_offset = 1
        else:
            # Check for "next <weekday>" or plain weekday names (including abbreviations)
            eng_days = {k: v for k, v in WEEKDAYS_CN.items() if k.isalpha() and (len(k) >= 3 or k in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'))}  # full names and abbr
            if 'next' in text_lower:
                for eng_day, num in eng_days.items():
                    if eng_day in text_lower:
                        today_weekday = base_date.weekday()
                        days_ahead = num - today_weekday
                        if days_ahead <= 0:
                            days_ahead += 7
                        day_offset = days_ahead + 7  # "next" adds 7
                        break
            else:
                for eng_day, num in eng_days.items():
                    if eng_day in text_lower:
                        today_weekday = base_date.weekday()
                        days_ahead = num - today_weekday
                        if days_ahead <= 0:
                            days_ahead += 7
                        day_offset = days_ahead
                        break

    target_date = base_date + timedelta(days=day_offset)

    # 提取时间
    hour = 9  # 默认上午9点
    minute = 0

    # If hour is still default 9, try English time patterns (e.g., "3pm", "3:30", "10am")
    if hour == 9 and minute == 0:
        # Pattern: hour optionally with minutes, optional am/pm
        m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\.?', text, re.IGNORECASE)
        if m:
            hr = int(m.group(1))
            mn = int(m.group(2) or 0)
            ampm = m.group(3)
            if ampm:
                ampm = ampm.lower()
                if ampm == 'pm' and hr < 12:
                    hr += 12
                elif ampm == 'am' and hr == 12:
                    hr = 0
            # Override hour and minute only if the hour is in a plausible range (0-23)
            if 0 <= hr <= 23:
                hour = hr
                minute = mn
                hour_captured = True
        # Also adjust based on "morning"/"afternoon"/"evening" if hour still default?
        # This may override if specific hour not found but period present
        if hour == 9 and ('afternoon' in text or 'after noon' in text):
            hour = 14  # default afternoon
        elif hour == 9 and ('evening' in text or 'night' in text):
            hour = 19

    naive_dt = datetime.combine(target_date.date(), time(hour, minute))
    tz = ZoneInfo(USER_TIMEZONE)
    dt = naive_dt.replace(tzinfo=tz)

    # Round minutes to nearest 15-minute increment to avoid odd times (:04, :34, etc.)
    total_minutes = dt.hour * 60 + dt.minute
    rounded_total = int(round(total_minutes / 15.0) * 15)
    # Handle day rollover if rounding pushes past midnight
    if rounded_total >= 24 * 60:
        rounded_total -= 24 * 60
        dt += timedelta(days=1)
    new_hour = (rounded_total // 60) % 24
    new_minute = rounded_total % 60
    dt = dt.replace(hour=new_hour, minute=new_minute)

    return dt

def find_busy_slots(service, start_dt: datetime, end_dt: datetime):
    """
    查询指定时间段内已有事件（busy slots）
    返回：list of {start, end} (all timezone-aware in UTC)
    """
    # 确保输入是 UTC aware
    utc_tz = ZoneInfo('UTC')
    local_tz = ZoneInfo(USER_TIMEZONE)

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=local_tz)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=local_tz)

    # 转换为 UTC ISO 格式
    time_min = start_dt.astimezone(utc_tz).isoformat()
    time_max = end_dt.astimezone(utc_tz).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        busy_slots = []
        for ev in events:
            # 忽略 cancelled 的事件
            if ev.get('status') == 'cancelled':
                continue
            start = ev['start'].get('dateTime')
            end = ev['end'].get('dateTime')
            if start and end:
                # parse as UTC (handle 'Z' suffix)
                start_str = start.replace('Z', '+00:00') if 'Z' in start else start
                end_str = end.replace('Z', '+00:00') if 'Z' in end else end
                start_utc = datetime.fromisoformat(start_str).astimezone(utc_tz)
                end_utc = datetime.fromisoformat(end_str).astimezone(utc_tz)
                busy_slots.append({
                    'start': start_utc,
                    'end': end_utc,
                    'summary': ev.get('summary', '无主题')
                })
        return busy_slots
    except HttpError as e:
        print(f"查询日历失败: {e}")
        return []

def check_conflict(service, proposed_start: datetime, duration_minutes: int = 30):
    """
    检查 proposed_start 时间是否有冲突
    返回：(冲突?, 冲突事件列表)
    """
    proposed_end = proposed_start + timedelta(minutes=duration_minutes)

    # 查询从 proposed_start 往前1天到往后1天的事件（足够覆盖）
    query_start = proposed_start - timedelta(hours=12)
    query_end = proposed_end + timedelta(hours=12)

    busy_slots = find_busy_slots(service, query_start, query_end)

    utc_tz = ZoneInfo('UTC')
    conflicts = []
    for slot in busy_slots:
        # 确保比较时区一致：将 slot 转为 UTC 与 proposed (already aware) 比较
        slot_start_utc = slot['start'].astimezone(utc_tz)
        slot_end_utc = slot['end'].astimezone(utc_tz)
        prop_start_utc = proposed_start.astimezone(utc_tz)
        prop_end_utc = proposed_end.astimezone(utc_tz)

        # 检查重叠
        if not (prop_end_utc <= slot_start_utc or prop_start_utc >= slot_end_utc):
            conflicts.append(slot)

    return len(conflicts) > 0, conflicts

def find_existing_event(service, start_dt: datetime, attendees: list, tolerance_minutes: int = 5):
    """
    Check if an event already exists with similar start time and attendees to prevent duplicates.
    Returns the existing event or None.
    """
    # Search window: ± tolerance around start time
    query_start = start_dt - timedelta(minutes=tolerance_minutes)
    query_end = start_dt + timedelta(minutes=tolerance_minutes)

    utc_tz = ZoneInfo('UTC')
    time_min = query_start.astimezone(utc_tz).isoformat()
    time_max = query_end.astimezone(utc_tz).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=20
        ).execute()
        events = events_result.get('items', [])
    except HttpError:
        return None

    # Normalize incoming attendees set (lowercase)
    incoming_attendees_set = set(email.lower() for email in attendees)

    for ev in events:
        # Skip cancelled events
        if ev.get('status') == 'cancelled':
            continue
        ev_start = ev['start'].get('dateTime')
        if not ev_start:
            continue
        # Compare start time within tolerance
        ev_start_dt = datetime.fromisoformat(ev_start.replace('Z', '+00:00'))
        ev_start_utc = ev_start_dt.astimezone(utc_tz)
        target_utc = start_dt.astimezone(utc_tz)
        if abs((ev_start_utc - target_utc).total_seconds()) > tolerance_minutes * 60:
            continue
        # Compare attendees (case-insensitive)
        ev_attendees = set(a['email'].lower() for a in ev.get('attendees', []))
        if ev_attendees != incoming_attendees_set:
            continue
        # Match found
        return ev
    return None
    """
    检查 proposed_start 时间是否有冲突
    返回：(冲突?, 冲突事件列表)
    """
    proposed_end = proposed_start + timedelta(minutes=duration_minutes)

    # 查询从 proposed_start 往前1天到往后1天的事件（足够覆盖）
    query_start = proposed_start - timedelta(hours=12)
    query_end = proposed_end + timedelta(hours=12)

    busy_slots = find_busy_slots(service, query_start, query_end)

    utc_tz = ZoneInfo('UTC')
    conflicts = []
    for slot in busy_slots:
        # 确保比较时区一致：将 slot 转为 UTC 与 proposed (already aware) 比较
        slot_start_utc = slot['start'].astimezone(utc_tz)
        slot_end_utc = slot['end'].astimezone(utc_tz)
        prop_start_utc = proposed_start.astimezone(utc_tz)
        prop_end_utc = proposed_end.astimezone(utc_tz)

        # 检查重叠
        if not (prop_end_utc <= slot_start_utc or prop_start_utc >= slot_end_utc):
            conflicts.append(slot)

    return len(conflicts) > 0, conflicts

def create_meeting_event(
    service,
    summary: str,
    start_dt: datetime,
    duration_minutes: int = 30,
    attendees: list = None,
    description: str = "",
    timezone: str = USER_TIMEZONE
):
    """
    创建会议事件（含 Google Meet 链接）
    start_dt: naive datetime (按 timezone 解释)
    """
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    # 构建英文描述，明确组织者为 Jessie (bot)
    full_description = f"""Meeting: {summary}

Organizer: Jessie, Meeting Coordinator (bot) at FounderGraph AI

Participants: {', '.join(attendees) if attendees else 'None'}

This meeting was scheduled by Jessie, Meeting Coordinator (bot) at FounderGraph AI."""

    event = {
        'summary': summary,
        'description': full_description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': timezone,
        },
        'conferenceData': {
            'createRequest': {
                'requestId': f'req-{int(datetime.now().timestamp()*1000)}',
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
    }

    if attendees:
        event['attendees'] = [{'email': email} for email in attendees]

    try:
        created = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all'  # 给所有参与者发送邀请
        ).execute()

        result = {
            'id': created.get('id'),
            'summary': created.get('summary'),
            'start': created.get('start'),
            'end': created.get('end'),
            'htmlLink': created.get('htmlLink'),
            'meetLink': None
        }

        # 提取 Meet 链接
        entry_points = created.get('conferenceData', {}).get('entryPoints', [])
        for ep in entry_points:
            if ep.get('entryPointType') == 'video':
                result['meetLink'] = ep.get('uri')
                break

        return result
    except HttpError as e:
        print(f"创建事件失败: {e}")
        return None

def send_email(to_email: str, subject: str, body: str):
    """
    通过 Gmail API 发送邮件
    需要启用 Gmail API 并配置 domain-wide delegation
    """
    try:
        service = get_google_service(api_name='gmail', api_version='v1',
                                    scopes=['https://www.googleapis.com/auth/gmail.send'])
        message = f"""From: Jessie (bot) <jessie@foundergraphai.com>
To: {to_email}
Subject: {subject}
Content-Type: text/plain; charset="UTF-8"

{body}"""
        encoded_message = message.encode('utf-8')
        import base64
        message_bytes = base64.urlsafe_b64encode(encoded_message).decode('utf-8')
        body = {'raw': message_bytes}
        service.users().messages().send(userId='me', body=body).execute()
        return True
    except Exception as e:
        print(f"发送邮件失败: {e}")
        return False

def list_upcoming_events(days_ahead: int = 7, max_results: int = 20):
    """
    列出未来几天的 upcoming calendar events
    返回：格式化字符串 (人类可读)
    """
    try:
        service = get_google_service()
    except Exception as e:
        return f"❌ Calendar service unavailable: {e}"

    # 时间范围：现在 到 days_ahead 天后
    utc_tz = ZoneInfo('UTC')
    local_tz = ZoneInfo(USER_TIMEZONE)
    now_local = datetime.now(local_tz)
    time_min = now_local.astimezone(utc_tz).isoformat()
    time_max = (now_local + timedelta(days=days_ahead)).astimezone(utc_tz).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=max_results
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return f"📅 未来 {days_ahead} 天内没有日程安排。"

        lines = [f"📅 接下来 {days_ahead} 天的日程 (共 {len(events)} 项):\n"]
        for idx, ev in enumerate(events, 1):
            if ev.get('status') == 'cancelled':
                continue
            start = ev['start'].get('dateTime')
            end = ev['end'].get('dateTime')
            if not start:
                # 全天事件
                start_display = ev['start'].get('date') + " (全⏳日)"
                start_dt = None
            else:
                # 解析为 datetime
                start_str = start.replace('Z', '+00:00') if 'Z' in start else start
                start_dt = datetime.fromisoformat(start_str).astimezone(local_tz)
                start_display = start_dt.strftime('%m月%d日 %H:%M')

            summary = ev.get('summary', '无主题')
            meet_link = None
            entry_points = ev.get('conferenceData', {}).get('entryPoints', [])
            for ep in entry_points:
                if ep.get('entryPointType') == 'video':
                    meet_link = ep.get('uri')
                    break

            line = f"{idx}. {summary}\n   🕐 {start_display}"
            if meet_link:
                line += f"\n   🔗 {meet_link}"
            lines.append(line)

        return "\n".join(lines)

    except HttpError as e:
        return f"❌ 查询日历失败: {e}"

def parse_meeting_request(text: str):
    """
    解析自然语言会议请求
    返回：{
        'summary': str,
        'attendees': list of emails,
        'time_text': str (原始时间描述),
        'start_dt': datetime (naive),
        'duration': int (minutes)
    }
    """
    import re

    # Disable Chinese parsing: if any Chinese characters present, return None
    if re.search(r'[\u4e00-\u9fff]', text):
        logger = logging.getLogger(__name__)
        logger.info("Chinese text detected; parse_meeting_request aborted")
        return None

    hour_captured = False
    period_hint = None
    if 'morning' in text:
        period_hint = 'morning'
    elif 'afternoon' in text or 'pm' in text:
        period_hint = 'afternoon'
    elif 'evening' in text or 'night' in text:
        period_hint = 'evening'

    # 1. 提取邮箱：优先从邮件头 (To:/Cc:) 解析，后备全文本扫描
    attendees = set()
    # 提取 To 行
    to_match = re.search(r'^To:\s*(.+)$', text, re.MULTILINE | re.IGNORECASE)
    if to_match:
        to_field = to_match.group(1)
        for name, addr in getaddresses([to_field]):
            if addr and '@' in addr:
                attendees.add(addr)
    # 提取 Cc 行
    cc_match = re.search(r'^Cc:\s*(.+)$', text, re.MULTILINE | re.IGNORECASE)
    if cc_match:
        cc_field = cc_match.group(1)
        for name, addr in getaddresses([cc_field]):
            if addr and '@' in addr:
                attendees.add(addr)

    # 后备：扫描全文本中的邮箱
    email_candidates = []
    at_positions = [m.start() for m in re.finditer('@', text)]
    for pos in at_positions:
        start = pos
        while start > 0:
            ch = text[start-1]
            if ch.isascii() and (ch.isalnum() or ch in '._%+-'):
                start -= 1
            else:
                break
        end = pos
        while end < len(text):
            ch = text[end]
            if ch.isascii() and (ch.isalnum() or ch in '.-@'):
                end += 1
            else:
                break
        candidate = text[start:end]
        if '@' in candidate:
            domain_part = candidate.split('@')[-1]
            if '.' in domain_part and ' ' not in domain_part and domain_part.split('.')[-1].isalpha():
                email_candidates.append(candidate)
    for cand in set(email_candidates):
        attendees.add(cand)

    attendees = list(attendees)

    # 2. 提取时间描述 - more robust and avoid false positives
    time_text = None
    hour_captured = False

    # Primary Chinese pattern with weekday first (requires a weekday indicator)
    chinese_time_pattern = r'(今天|明天|后天|下周一|下周二|下周三|下周[一二三四五六日]|周[一二三四五六日]|周一|周二|周三|周四|周五|周六|周日|mon|tue|wed|thu|fri|sat|sun)\s*(上午|下午|晚上)?\s*(\d{1,2})(?:点|[:：]|钟)?\s*(\d{0,2})'
    m = re.search(chinese_time_pattern, text, re.IGNORECASE)
    if m:
        time_text = m.group(0)
        hour_captured = True
    else:
        # Chinese numerals pattern (e.g., "三点")
        cn_num_pattern = r'(今天|明天|后天|下周一|下周二|下周三|下周[一二三四五六日]|周[一二三四五六日])\s*(上午|下午|晚上)?\s*([一二三四五六七八九十零]+)(?:点|钟)?'
        m2 = re.search(cn_num_pattern, text, re.IGNORECASE)
        if m2:
            cn_num_map = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10, '零':0}
            cn_num_str = m2.group(3)
            if len(cn_num_str) == 1:
                hour = cn_num_map.get(cn_num_str, 9)
            elif cn_num_str == '十':
                hour = 10
            else:
                hour = 9
            time_text = m2.group(0)
            hour_captured = True
            text = text.replace(cn_num_str, str(hour))
        else:
            # English relative patterns (require "tomorrow" or "next <weekday>" or explicit weekday)
            en_pattern = r'\b(tomorrow|next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b'
            m_en = re.search(en_pattern, text, re.IGNORECASE)
            if m_en:
                time_text = text  # Let parse_relative_date scan the full text for time info
            else:
                # No valid weekday indicator found — cannot reliably parse
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not find valid weekday/time pattern in request: {text[:200]!r}")
                return None

    # 3. 解析具体时间
    if not hour_captured:
        # Check for explicit hour in English format (e.g., "3pm", "10:30") anywhere in the text
        if re.search(r'\b\d{1,2}\s*(am|pm)\b', text, re.IGNORECASE):
            hour_captured = True
        # else: remain False — we will require explicit time

    # Only parse a full datetime if we captured an explicit hour; otherwise start_dt remains None
    if hour_captured:
        start_dt = parse_relative_date(time_text if time_text else text)

        # Validation: ensure parsed time is not in the distant past (likely a bug) and not more than 60 days in future
        now = datetime.now(start_dt.tzinfo)
        if start_dt < now - timedelta(hours=2):
            # Parsed a time that's already passed by more than 2 hours — likely incorrect
            logger = logging.getLogger(__name__)
            logger.warning(f"Parsed time {start_dt} is in the past; likely incorrect. Text snippet: {time_text or 'N/A'}")
            return None
        if start_dt > now + timedelta(days=60):
            logger = logging.getLogger(__name__)
            logger.warning(f"Parsed time {start_dt} is too far in future; likely incorrect. Text snippet: {time_text or 'N/A'}")
            return None
    else:
        start_dt = None

    # 4. 提取主题
    # 方法1: 明确"主题是..."格式
    summary_match = re.search(r'主题[是为：:]\s*([^\n,]+?)(?:用英文|in English|,|，|$)', text, re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip()
    else:
        # 方法2: 移除时间和邮箱后的剩余部分
        remaining = text
        if time_text:
            remaining = remaining.replace(time_text, '')
        for email in attendees:
            remaining = remaining.replace(email, '')
        # 移除常见动词
        remaining = remaining.strip(' .,，、的 用英文 in English')
        if remaining and len(remaining) < 30:
            summary = remaining
        else:
            # Fallback: use email subject or default
            summary = "Meeting"

    auto_mode = not hour_captured
    return {
        'summary': summary,
        'attendees': attendees,
        'time_text': time_text or text,
        'start_dt': start_dt,
        'duration': DEFAULT_DURATION,
        'auto': auto_mode,
        'preferred_period': period_hint
    }

# 主调度函数
def schedule_meeting(request_text: str, recipients: list = None):
    """
    Schedule a meeting from an email.
    Args:
        request_text: full email context (headers + body)
        recipients: explicit list of recipient emails (To + Cc) from the email.
                    If provided, it overrides any attendees parsed from the body.
    Returns: dict with meeting details or error string
    """
    # Extract summary from email subject
    subject_line = None
    for line in request_text.splitlines():
        if line.lower().startswith("subject:"):
            subject_line = line[7:].strip()  # len("subject:") = 7
            break
    if subject_line:
        clean_subject = re.sub(r"^(re|fwd?):\s*", "", subject_line, flags=re.IGNORECASE)
        clean_subject = clean_subject.strip(" .,\t\n")
        if clean_subject and len(clean_subject) < 60:
            summary = clean_subject
        else:
            summary = "Meeting scheduled by Jessie"
    else:
        summary = "Meeting scheduled by Jessie"

    """
    完整调度流程：解析 → 检查冲突 → 创建事件 → 返回结果
    返回：dict 或 error string
    """
    # 1. 解析
    parsed = parse_meeting_request(request_text)
    if not parsed:
        return "❌ Unable to parse meeting time. Please specify clearly, e.g., 'tomorrow 3pm with Alice' or 'next Tuesday 10am'"

    # Require explicit time (no fallback to 9am)
    if parsed.get('start_dt') is None:
        return "❌ Could not determine meeting time. Please include a specific time, e.g., 'tomorrow 3pm' or 'next Tuesday 10am'."

    # 2. Determine attendees: prefer explicit recipients over parser extraction
    attendees = []
    if recipients:
        # Use the provided recipient list, remove empty/invalid
        attendees = [e for e in recipients if e and '@' in e]
    else:
        attendees = parsed.get('attendees', [])

    # Remove bot's own email to avoid inviting itself as attendee
    try:
        attendees.remove(USER_EMAIL)
    except ValueError:
        pass

    # Add the sender (from email) to the meeting if not already present
    # Extract From header from the raw request text
    from_match = re.search(r'^From:\s*(.+)$', request_text, re.MULTILINE | re.IGNORECASE)
    if from_match:
        from_header = from_match.group(1).strip()
        # Extract email address from header (e.g., "Name <email>" or just "email")
        if '<' in from_header:
            sender_email = from_header.split('<')[-1].split('>')[0].strip()
        else:
            # Take the last whitespace-separated token as the email
            sender_email = from_header.strip().split()[-1]
        # Validate basic email format
        if '@' in sender_email and sender_email != USER_EMAIL and sender_email not in attendees:
            attendees.append(sender_email)

    # 3. 初始化日历服务
    try:
        service = get_google_service()
    except Exception as e:
        return f"❌ Calendar service unavailable: {e}"

    # 4. 检查冲突
    has_conflict, conflicts = check_conflict(service, parsed['start_dt'], parsed['duration'])
    if has_conflict:
        if parsed.get('auto'):
            # Auto mode: find an alternative slot on the same day
            alternative = find_available_slot(service, parsed['start_dt'].date(), parsed.get('preferred_period'), parsed['duration'])
            if alternative:
                # Use the alternative time
                parsed['start_dt'] = alternative
                has_conflict = False
            else:
                return "❌ No available slots on that day. Please try another day."
        else:
            conflict_list = "\n".join([f"  • {c['start'].strftime('%H:%M')}-{c['end'].strftime('%H:%M')}: {c['summary']}" for c in conflicts[:3]])
            return f"⚠️ Time conflict! Existing meetings:\n{conflict_list}\nPlease choose another time."

    # 5. 生成会议标题（尝试 LLM 增强）
    summary = generate_meeting_title(request_text, parsed.get('summary'))
    # 确保标题是英文（如果混入了中文，移除）
    summary = re.sub(r'[^\x00-\x7F]+', ' ', summary).strip()
    if not summary or len(summary) < 2:
        summary = "Meeting"

    # 5b. 幂等性检查：避免重复创建相同事件（基于开始时间和参与者）
    existing = find_existing_event(service, parsed['start_dt'], attendees, tolerance_minutes=10)
    if existing:
        # 构建现有事件的回复
        existing_start_utc = existing['start'].get('dateTime')
        existing_end_utc = existing['end'].get('dateTime')
        local_tz = ZoneInfo(USER_TIMEZONE)
        if existing_start_utc:
            start_dt_utc = datetime.fromisoformat(existing_start_utc.replace('Z', '+00:00'))
            start_local = start_dt_utc.astimezone(local_tz)
        if existing_end_utc:
            end_dt_utc = datetime.fromisoformat(existing_end_utc.replace('Z', '+00:00'))
            end_local = end_dt_utc.astimezone(local_tz)
        meet_link = None
        entry_points = existing.get('conferenceData', {}).get('entryPoints', [])
        for ep in entry_points:
            if ep.get('entryPointType') == 'video':
                meet_link = ep.get('uri')
                break
        existing_attendees = [a.get('email') for a in existing.get('attendees', [])]
        reply = f"""✅ Meeting already scheduled!

📅 Time: {existing_start_utc} - {existing_end_utc} (UTC)
🌍 Your local time: {start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%H:%M')} (Asia/Shanghai)

📍 Title: {existing.get('summary')}
👥 Participants: {', '.join(existing_attendees)}

🔗 Google Meet:
{meet_link or 'N/A'}

📋 Calendar event:
{existing.get('htmlLink')}

(Found existing event; no duplicate created.)"""
        return reply

    # 6. 创建事件
    event_info = create_meeting_event(
        service=service,
        summary=summary,
        start_dt=parsed['start_dt'],
        duration_minutes=parsed['duration'],
        attendees=attendees
        # description 已由 create_meeting_event 内部生成，无需传入
    )
    if not event_info:
        return "❌ Failed to create event. Please check logs."

    # 6. 准备 reply（英文）
    reply = f"""✅ Meeting scheduled!

📅 Time: {event_info['start']['dateTime']} - {event_info['end']['dateTime']} (UTC)
🌍 Your local time: {parsed['start_dt'].strftime('%Y-%m-%d %H:%M')} (Asia/Shanghai)

📍 Title: {event_info['summary']}
👥 Participants: {', '.join(attendees)}

🔗 Google Meet:
{event_info['meetLink']}

📋 Calendar event:
{event_info['htmlLink']}

(A meeting invitation has been sent to all participants via email.)"""

    return reply

# 命令行测试
def find_available_slot(service, target_date, preferred_period=None, duration_minutes=DEFAULT_DURATION):
    """
    在指定日期和偏好时段内查找空闲时间槽
    返回：timezone-aware datetime 或 None
    """
    local_tz = ZoneInfo(USER_TIMEZONE)
    # 定义搜索窗口
    if preferred_period == 'morning':
        start_hour = 9
        end_hour = 12
    elif preferred_period == 'afternoon':
        start_hour = 14
        end_hour = 17
    elif preferred_period == 'evening':
        start_hour = 19
        end_hour = 21
    else:
        start_hour = 9
        end_hour = 17

    candidate_start = datetime.combine(target_date, time(start_hour, 0)).replace(tzinfo=local_tz)
    while candidate_start.hour < end_hour:
        candidate_end = candidate_start + timedelta(minutes=duration_minutes)
        conflict, _ = check_conflict(service, candidate_start, duration_minutes)
        if not conflict:
            return candidate_start
        candidate_start += timedelta(minutes=30)
    return None

if __name__ == '__main__':
    test_text = "明天下午3点和 yuchuanxu@hotmail.com 开会，主题是产品评审"
    result = schedule_meeting(test_text)
    print(result)