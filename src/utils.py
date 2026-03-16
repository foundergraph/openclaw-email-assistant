"""Utility functions for email processing."""

import base64
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def decode_mime_header(value: str) -> str:
    """Decode RFC 2047 encoded email headers."""
    if not value:
        return ''
    try:
        from email.header import decode_header
        decoded_parts = decode_header(value)
        result = ''
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                try:
                    result += part.decode(encoding or 'utf-8', errors='replace')
                except:
                    result += part.decode('utf-8', errors='replace')
            else:
                result += part
        return result
    except Exception as e:
        logger.warning(f"Failed to decode header: {e}, returning raw")
        return value

def extract_email_address(header: str) -> str:
    """Extract email address from a header like 'Name <email>' or just 'email'."""
    if not header:
        return ''
    match = re.search(r'<(.+?)>', header)
    if match:
        return match.group(1).strip()
    parts = header.strip().split()
    if parts:
        last = parts[-1]
        if '@' in last:
            return last
    return header.strip()

def parse_email_address_list(header: str) -> List[str]:
    """Parse comma-separated email addresses from To/Cc headers using getaddresses."""
    if not header:
        return []
    try:
        from email.utils import getaddresses
        results = getaddresses([header])
        return [addr for name, addr in results if addr and '@' in addr]
    except Exception:
        # Fallback to simple split-based method
        addresses = []
        for part in header.split(','):
            addr = extract_email_address(part)
            if addr and '@' in addr:
                addresses.append(addr)
        return addresses

def extract_email_body(payload: Dict[str, Any]) -> str:
    """Extract plain text body from Gmail message payload."""
    try:
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        elif 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to extract body: {e}")
    return "[Could not extract email body]"

def strip_thinking(text: str) -> str:
    """Remove AI thinking/analysis markers from the start of a message."""
    if not text:
        return text

    lines = text.splitlines()

    # Patterns that unambiguously indicate meta/thinking output
    thinking_starters = [
        r"^let me think",
        r"^i'll think",
        r"^thinking",
        r"^first,?\s+i(?:'?ll| will)? (?:check|look|verify|see)",
        r"^first,?\s*let me",
        r"^i need to (?:think|check|look|consider)",
        r"^checking",
        r"^searching",
        r"^one moment",
        r"^hold on",
        r"^ok,?\s*i(?:'?ll| will)",
        r"^great!?\s*i(?:'?ll| will)",
        r"^perfect!?\s*i(?:'?ll| will)",
        r"^success!",
        r"^done\.?",
        r"^< ?li ?>",
        r"^<ol>",
        r"^<ul>",
    ]
    pattern = re.compile("|".join(thinking_starters), re.IGNORECASE)

    # Remove leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)

    # Remove thinking lines; if all lines removed, return original
    removed = 0
    while lines and pattern.match(lines[0].strip()):
        lines.pop(0)
        removed += 1

    if removed and not any(line.strip() for line in lines):
        return text.strip()

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"^(<[ou]l>)+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def fill_placeholders(obj: Any, mapping: Dict[str, str]) -> Any:
    """Recursively replace placeholders like {key} in dicts/lists/strings."""
    try:
        if isinstance(obj, dict):
            return {k: fill_placeholders(v, mapping) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [fill_placeholders(item, mapping) for item in obj]
        elif isinstance(obj, str):
            result = obj
            for key, val in mapping.items():
                placeholder = f'{{{key}}}'
                result = result.replace(placeholder, str(val))
            return result
        else:
            return obj
    except Exception as e:
        logger.error(f"Failed to fill placeholders: {e}")
        return obj
