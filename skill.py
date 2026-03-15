"""OpenClaw Email Assistant Skill

An AI-powered email bot that manages inbox, schedules meetings from natural language,
and handles bounce notifications.
"""

import os
import sys

def main(config_path: str, openclaw_client=None):
    """
    OpenClaw skill entry point.

    Args:
        config_path: Path to YAML configuration file
        openclaw_client: OpenClaw gateway client (optional, not used directly)
    """
    # Add the skill directory to path for relative imports
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    if skill_dir not in sys.path:
        sys.path.insert(0, skill_dir)

    from src.email_bridge import EmailBridge

    bridge = EmailBridge(config_path, openclaw_client)
    bridge.start()
