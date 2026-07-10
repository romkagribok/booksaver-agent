---
unit: 002-booking-com-price-monitor
bolt: 003-booking-com-price-monitor
id: ADR-007
title: Playwright for browser automation
status: accepted
updated: 2026-07-05T00:00:00Z
---

# ADR-007: Playwright for browser automation

## Context

US-005 requires opening Booking.com manage-booking pages in a real browser the daemon
controls; US-004 requires persisting and restoring the login session. Candidates:
Playwright, Selenium, pyppeteer/Puppeteer-via-CDP, raw HTTP requests.

## Decision

Use **Playwright for Python** with bundled Chromium.

## Rationale

- **Session handling is first-class**: `context.cookies()` / `context.add_cookies()` and
  `storage_state` give exactly the export/import cycle US-004 needs, without manual CDP work.
- **Headed and headless from one API**: `booksaver auth` needs a visible browser for manual
  login; scheduled checks need headless. Playwright switches with one flag.
- **Auto-waiting** drastically reduces flaky navigation failures against a heavy dynamic
  site like Booking.com, which directly serves US-014 (fewer spurious failures to handle).
- **Maintained Python API with sync mode** — no Selenium driver-binary management
  (Playwright ships and pins its own browsers via `playwright install`).
- Raw HTTP is a non-starter: Booking.com manage pages are behind JS-rendered auth flows,
  and the standards mandate browser automation, not API scraping.

## Consequences

- First third-party runtime dependency with a post-install step: `playwright install chromium`
  (documented in CLAUDE.md and README).
- Bundled Chromium adds ~150 MB local disk — acceptable for a personal local tool.
- Bot-detection/captcha remain possible; handled as `CheckFailed(auth_required)` per US-014,
  with `booksaver auth` as the recovery path.
