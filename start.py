#!/usr/bin/env python3
import sys
import os

def main():
    # Add the skill directory to path for relative imports
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    if skill_dir not in sys.path:
        sys.path.insert(0, skill_dir)

    # Config path relative to this file
    config_path = os.path.join(skill_dir, "config", "local.yaml")
    
    # Print debug info
    print(f"DEBUG: Loading config from: {config_path}")
    print(f"DEBUG: Config exists: {os.path.exists(config_path)}")

    from src.email_bridge import EmailBridge

    bridge = EmailBridge(config_path, None)
    bridge.start()

if __name__ == "__main__":
    main()
