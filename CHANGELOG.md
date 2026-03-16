# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of OpenClaw Email Assistant

## [0.2.0] - 2026-03-16

### Fixed
- Recipient parsing now uses `email.utils.getaddresses` for robustness; CC recipients are correctly included in meeting invites.
- `strip_thinking` function is less aggressive, preserving legitimate message openings and preventing empty replies.

### Changed
- Meeting scheduling now properly propagates recipient list (To + Cc) to the Google Meetings Scheduler skill.
- Replies no longer get stripped when they begin with common conversational phrases.

## [0.1.0] - 2026-03-07

### Added
- Core email polling and processing
- Natural language meeting scheduling (Chinese/English)
- Bounce detection and handling
- Notion task creation integration
- OpenClaw skill integration
