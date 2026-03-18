"""Utility functions for email processing."""

import base64
import re
import logging
from typing import List, Dict, Any, Optional

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
    """Extract plain text body from Gmail message payload (recursive)."""
    import logging
    logger = logging.getLogger(__name__)
    
    def _extract(part: Dict[str, Any]) -> Optional[str]:
        mime = part.get('mimeType', '')
        if mime == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to decode body part: {e}")
                    return None
        # If multipart, recurse into parts
        if 'parts' in part:
            for sub in part['parts']:
                result = _extract(sub)
                if result:
                    return result
        return None

    try:
        result = _extract(payload)
        if result:
            return result
        # Fallback: try to get any text/plain at top level
        if 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            try:
                return base64.urlsafe_b64decode(data).decode('utf-8')
            except Exception as e:
                logger.warning(f"Failed to decode fallback body: {e}")
        # Fallback to text/html: strip tags
        def _extract_html(part: Dict[str, Any]) -> Optional[str]:
            mime = part.get('mimeType', '')
            if mime == 'text/html':
                data = part.get('body', {}).get('data', '')
                if data:
                    try:
                        html = base64.urlsafe_b64decode(data).decode('utf-8')
                    except UnicodeDecodeError:
                        # Fallback decoding with replacement characters or latin1
                        try:
                            html = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        except Exception:
                            html = base64.urlsafe_b64decode(data).decode('latin1')
                        # Simple strip of tags
                        import re
                        text = re.sub(r'<[^>]+>', '', html)
                        # Collapse whitespace
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text
                    except Exception as e:
                        logger.warning(f"Failed to decode HTML fallback: {e}")
                        return None
            if 'parts' in part:
                for sub in part['parts']:
                    result = _extract_html(sub)
                    if result:
                        return result
            return None
        html_result = _extract_html(payload)
        if html_result:
            return html_result
    except Exception as e:
        logger.error(f"Failed to extract body: {e}", exc_info=True)
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
        r"^i'll check",
        r"^i've reviewed",
        r"^based on my (?:check|review)",
        r"^i've checked",
        r"^reviewing",
        r"^analyzing",
        r"^reading",
        r"^understanding",
        r"^memory",
        r"^context",
        # Extended: any "I'll/Let me/I'm/I've" + action verbs (including help/assist/check/etc)
        r"^i'll (?:use|call|invoke|trigger|run|execute|process|handle|schedule|create|send|lookup|find|get|fetch|generate|help|assist|attempt|try|check|see|verify|look|understand|determine)",
        r"^i will (?:use|call|invoke|trigger|run|execute|process|handle|schedule|create|send|lookup|find|get|fetch|generate|help|assist|attempt|try|check|see|verify|look|understand|determine)",
        r"^i'm (?:using|calling|invoking|triggering|running|executing|processing|handling|scheduling|creating|sending|looking up|fetching|generating|helping|assisting|attempting|trying|checking|seeing|verifying|looking|understanding|determining)",
        r"^i've (?:used|called|invoked|triggered|ran|executed|processed|handled|scheduled|created|sent|looked up|fetched|generated|helped|assisted|attempted|tried|checked|seen|verified|looked|understood|determined)",
        r"^let me (?:use|call|invoke|trigger|run|execute|process|handle|schedule|create|send|lookup|find|get|fetch|generate|help|assist|attempt|try|check|see|verify|look|understand|determine)",
        r"^using (?:the )?(?:skill|tool|function|system|api)",
        r"^calling (?:the )?(?:skill|tool|function|system|api)",
        r"^processing (?:with|via|using)",
        r"^generating ",
        r"^creating ",
        r"^running ",
        r"^executing ",
        r"^invoking ",
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
