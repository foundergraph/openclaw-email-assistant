# Security Policy

## Supported Versions

Currently only the latest version on the `main` branch is supported for security updates.

## Reporting a Vulnerability

We take security issues seriously. If you discover a vulnerability, please report it privately.

**Please do not open a public GitHub issue** for security vulnerabilities.

### How to Report

Email: **yuchuanxu@example.com** (replace with your actual email)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

You can expect a response within 48 hours. If the issue is confirmed, we will:

1. Acknowledge receipt
2. Work on a fix in a private branch
3. Coordinate disclosure timeline (typically 90 days)
4. Credit you in the release notes (if desired)

## Security Practices

- OAuth tokens and credentials are never committed
- No logging of email bodies or sensitive PII
- Dependencies are pinned in `requirements.txt` / `pyproject.toml`
- Users are responsible for their own Gmail API credentials and API keys

## Best Practices for Deployers

1. Use a dedicated Gmail account for the bot (not personal)
2. Restrict OAuth client to that account only
3. Store credentials and tokens outside the repository (environment variables or separate config)
4. Set appropriate file permissions (600) on credential files
5. Keep dependencies updated (use `pip list --outdated`)
6. Monitor logs for unusual activity
7. Use HTTPS for your OpenClaw gateway if exposed externally

## Known Limitations

- This skill requires service account credentials with domain-wide delegation if used with G Suite. For personal Gmail, OAuth client is used.
- The bot responds to whitelisted senders or mentions — configure this appropriately.
- Meeting scheduling relies on Google Calendar API; no cancellation/modification support yet.
