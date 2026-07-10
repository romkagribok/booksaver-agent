---
unit: 003-savings-detection-notifications
bolt: 004-savings-detection-notifications
id: ADR-011
title: Stdlib-only notification transports (smtplib + urllib Telegram Bot API)
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-011: Stdlib-only notification transports

## Context

US-009 requires email and Telegram alerts. Candidates: `requests` +
`python-telegram-bot` (or similar SDKs), vs Python's stdlib `smtplib`/`email` and
`urllib.request` against the Telegram Bot API directly.

## Decision

Use **stdlib only**: `smtplib` with STARTTLS for email, `urllib.request` POSTing to
`https://api.telegram.org/bot{token}/sendMessage` for Telegram.

## Rationale

- Both operations are a single small request; SDKs add dependency weight for features
  (bots, polling, webhooks, sessions) the MVP does not use.
- Consistent with ADR-003 (stdlib-first): playwright/anthropic were justified because
  the stdlib genuinely cannot drive a browser or call an LLM well; it *can* send an
  email and one HTTPS POST perfectly well.
- The `Notifier` port isolates the choice — a future Telegram-bot interface (the
  preferred long-term UX) would arrive as a new adapter/unit, likely with a real SDK,
  without touching detection logic.

## Consequences

- Telegram support is send-only (fine: MVP alerts are one-way; interactive bot is
  post-MVP direction).
- SMTP config lives in `config.toml` (host/port/username), password in
  `BOOKSAVER_SMTP_PASSWORD` (ADR-002 pattern).
- No retry/backoff library; a failed send is logged and visible via
  `booksaver savings list` (`notified_at` empty). Acceptable for a personal tool
  checking every few hours.
