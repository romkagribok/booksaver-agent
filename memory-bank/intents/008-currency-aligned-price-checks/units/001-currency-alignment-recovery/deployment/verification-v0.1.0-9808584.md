---
version: v0.1.0-9808584
environment: production
verified: 2026-07-19T01:04:31Z
status: passed
---

# Verification Report: Currency Alignment Recovery

## Health Checks

- ✅ Source checkout matches release commit `9808584e64d2f61d333e84d3f26ac4ffee8a6cf2`.
- ✅ Docker Compose configuration validates.
- ✅ Container `booksaver` is running and Docker health status is `healthy`.
- ✅ Runtime imports expose `currency_mismatch` and `align_currency` from the deployed package.
- ✅ BookSaver configuration validates with the mounted `/data` directory and 12-hour interval.
- ✅ Telegram Bot API `getMe` succeeds for `@booksaver_agent_bot` without exposing the token.

## Startup and Resource Smoke Checks

- ✅ Telegram bot gateway reports enabled.
- ✅ Daemon starts cleanly and handles the expected absence of an authenticated Booking.com session by
  retaining logged-out public-rate behavior.
- ✅ No error, traceback, crash-loop, or restart appears in post-deployment logs.
- ✅ Immediate resource snapshot: 0.01% CPU and 83.47 MiB of 1 GiB memory.

## Acceptance Boundary

Automated deployment verification passed. The product-owner production acceptance test is a Telegram
`/checknow` for the reproduced booking. Expected outcomes are either a verified same-baseline-currency
price result or an actionable `currency_mismatch`; unlike-currency savings must never be emitted.

## Conclusion

Passed. The release is healthy and ready for Telegram acceptance testing.
