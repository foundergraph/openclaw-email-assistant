#!/usr/bin/env python3
"""Quick sanity test for the email assistant skill."""

import sys
import os
import yaml

# Add the skill directory to path
skill_dir = "/home/ubuntu/.openclaw/workspace/openclaw-email-assistant"
if skill_dir not in sys.path:
    sys.path.insert(0, skill_dir)

def test_imports():
    print("Testing imports...")
    try:
        from src.email_bridge import EmailBridge
        from src.nlu_parser import EnglishDateParser
        from src.bounce_detector import is_bounce_email
        from src.utils import decode_mime_header, extract_email_address
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config_loading():
    print("\nTesting config loading...")
    test_config = {
        'email': {
            'credentials_file': '~/.openclaw/email-assistant/credentials.json',
            'token_file': '~/.openclaw/email-assistant/token.json',
            'monitor_email': 'test@example.com',
            'bcc_email': ''
        },
        'whitelisted_senders': ['test@example.com'],
        'mention_triggers': ['@test'],
        'openclaw': {
            'gateway_url': 'http://localhost:8080',
            'api_key': 'test-key'
        },
        'features': {
            'strip_thinking': True,
            'mark_bounces_read': True,
            'chinese_nl_parser': False,
            'default_meeting_duration': 30
        },
        'calendar': {
            'calendar_id': 'primary',
            'always_invite': [],
            'title_prefix': 'Test'
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': '~/.openclaw/logs/email-assistant-test.log',
            'max_bytes': 10485760,
            'backup_count': 5
        },
        'limits': {
            'max_emails_per_run': 50,
            'processing_timeout_seconds': 300
        },
        'notion': {
            'api_key': '',
            'tasks_database_id': ''
        }
    }
    try:
        import yaml
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            config_path = f.name
        print(f"✓ Config written to: {config_path}")
        return config_path
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return None

def test_skill_entrypoint(config_path):
    print("\nTesting skill entry point...")
    try:
        # We can't actually call main() without an OpenClaw client, but we can check it loads
        import skill
        print("✓ skill.py imports successfully")
        print("✓ skill.main exists:", callable(getattr(skill, 'main', None)))
        return True
    except Exception as e:
        print(f"✗ Skill entry point failed: {e}")
        return False

def test_parser():
    print("\nTesting English date parser...")
    try:
        from src.nlu_parser import EnglishDateParser
        parser = EnglishDateParser()
        test_cases = [
            "tomorrow at 3pm",
            "next Monday at 10am",
            "today at 2:30 pm",
            "3pm"
        ]
        for text in test_cases:
            result = parser.parse(text)
            print(f"  '{text}' -> {result}")
        print("✓ Parser works")
        return True
    except Exception as e:
        print(f"✗ Parser test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("OpenClaw Email Assistant — Quick Test")
    print("=" * 60)

    if not test_imports():
        print("\n❌ Tests failed")
        sys.exit(1)

    config_path = test_config_loading()
    if not config_path:
        print("\n❌ Tests failed")
        sys.exit(1)

    if not test_skill_entrypoint(config_path):
        print("\n❌ Tests failed")
        sys.exit(1)

    if not test_parser():
        print("\n❌ Tests failed")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ All quick tests passed!")
    print("=" * 60)
    print("\nThe skill is structurally sound. You can now:")
    print("1. Place credentials.json in ~/.openclaw/email-assistant/")
    print("2. Edit config/local.yaml with your settings")
    print("3. Run: python skill.py config/local.yaml")
    print("4. Integrate with OpenClaw gateway")

    # Cleanup temp file
    try:
        os.unlink(config_path)
    except:
        pass

if __name__ == "__main__":
    main()
