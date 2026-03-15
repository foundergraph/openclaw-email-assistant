#!/usr/bin/env bash
# Setup script for OpenClaw Email Assistant

set -e

echo "=== OpenClaw Email Assistant Setup ==="

# Create config directory if not exists
mkdir -p ~/.openclaw/email-assistant

# Check for credentials
if [ ! -f ~/.openclaw/email-assistant/credentials.json ]; then
    echo "⚠️  No credentials.json found."
    echo "Please download from Google Cloud Console and place at:"
    echo "  ~/.openclaw/email-assistant/credentials.json"
    exit 1
fi

echo "✓ Credentials found"

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Create default config if not exists
if [ ! -f config/local.yaml ]; then
    cp config/default.yaml config/local.yaml
    echo "✓ Created config/local.yaml (please edit with your settings)"
fi

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/local.yaml with your email and preferences"
echo "2. Run: python skill.py config/local.yaml (to authorize)"
echo "3. Add to openclaw.json and restart gateway"
