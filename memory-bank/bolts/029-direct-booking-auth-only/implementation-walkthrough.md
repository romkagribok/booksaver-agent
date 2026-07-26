---
stage: implement
bolt: 029-direct-booking-auth-only
created: 2026-07-26T21:18:54.000Z
---

## Implementation Walkthrough: Direct Booking Authentication Only

### Summary

The transient remote-auth browser now accepts only Booking.com-owned document navigation across the
main page, child frames, and popups.
BookSaver-owned Telegram and viewer messages proactively direct users to Booking.com email/password
and explain that external providers are disabled.

### Structure Overview

The browser runner's context-level route remains the enforcement point installed before page
creation. Stable guidance lives in the Telegram `/connect` launch flow and the application-owned
viewer state rather than depending on Booking.com's page layout.

### Completed Work

- [x] `src/booksaver/infrastructure/remote_auth/browser_runner.py` - Replaces provider exceptions
  with an exact Booking.com document-navigation hostname boundary.
- [x] `src/booksaver/infrastructure/telegram/connect_command.py` - Adds direct-login-only launch and
  reconnect guidance.
- [x] `src/booksaver/application/remote_auth.py` - Adds direct-login-only ready/connected viewer
  guidance.
- [x] `tests/unit/test_remote_browser_runner.py` - Covers Booking hosts, providers, arbitrary and
  lookalike hosts, popup and child-frame policy, external resources, and downloads.
- [x] `tests/unit/telegram/test_connect_command.py` - Covers typed and callback launch guidance.
- [x] `tests/unit/test_remote_auth.py` - Covers ready/connected viewer guidance.

### Key Decisions

- **Booking-owned navigation allowlist**: Exact host/subdomain matching covers main pages, child
  frames, and popups without maintaining a provider denylist.
- **Preserve non-navigation resources**: Direct login can continue using Booking.com's external
  scripts, images, and other dependencies.
- **BookSaver-owned guidance**: Messaging remains stable across Booking.com layout changes.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

Provider buttons are not hidden with selectors. If selected, their main-page, child-frame, or popup
document is blocked by the browser policy; the visible guidance tells users which path to choose
before that interaction.
