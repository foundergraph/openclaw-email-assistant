# Contributing to OpenClaw Email Assistant

Thank you for considering a contribution! This document provides guidelines and information for contributors.

## How to Contribute

### Reporting Bugs

- Check existing issues to avoid duplicates
- Open a new issue with:
  - Clear description of the problem
  - Steps to reproduce
  - Expected vs actual behavior
  - Environment details (OS, Python version, OpenClaw version)
  - Logs (with sensitive data redacted)

### Suggesting Features

- Open an issue first to discuss the idea
- Explain the use case and why it's valuable
- Consider if it fits the project's scope (email automation for OpenClaw)

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Ensure code passes linting and tests (`pytest tests/`)
5. Update documentation if needed
6. Submit a PR with a clear description

**PR Guidelines:**
- Keep changes focused; one PR per feature/fix
- Follow existing code style (PEP 8)
- Add tests for new functionality
- Update README or docs for user-facing changes

## Development Setup

```bash
git clone https://github.com/yourusername/openclaw-email-assistant.git
cd openclaw-email-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest flake8
cp config/default.yaml config/local.yaml
# Edit config/local.yaml with your settings
```

## Testing

Run tests:

```bash
pytest tests/ -v
```

Lint:

```bash
flake8 . --max-line-length=127
```

## Codebase Structure

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for an overview.

Key modules:
- `src/email_bridge.py` — core email processing
- `src/nlu_parser.py` — date/time parsing
- `src/bounce_detector.py` — bounce detection
- `src/utils.py` — utilities
- `skill.py` — OpenClaw entry point

## Configuration

Configuration is in `config/local.yaml` (copy from `default.yaml`). See `docs/SETUP.md` for details.

## Security

- Never commit credentials or tokens
- Be mindful of PII in logs
- Follow least-privilege principle for OAuth scopes

## Questions?

Open an issue or join OpenClaw Discord.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see LICENSE).
