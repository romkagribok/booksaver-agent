---
id: US-035
status: complete
implemented: true
---

# US-035 Logged-out checks with optional cookie import

**Intent:** `003-telegram-interface`
**Unit:** `005-vps-deployment`
**Status:** Ready
**Tag:** Phase 3

## Story

**As a** user whose monitor runs on a display-less VPS
**I want** checks to work without a Booking.com login, with an optional cookie import for member rates
**So that** monitoring works even though headed `booksaver auth` is impossible there

**Acceptance criteria**

- In logged-out mode the search journey (search → results → property → room table) runs with no saved session and produces real public bookable totals; no `AUTH_REQUIRED` failures occur in this mode
- Session mode (logged-out vs imported-cookies) is explicit per deployment/user, visible in `/status`
- A documented import path lets a user export Booking.com cookies from their own browser and load them (CLI file import; optionally via bot as a file upload with immediate message deletion)
- Imported cookies are stored with the same care as sessions today; expiry produces a clear re-import prompt, not silent price degradation
- Prices found logged-out are labeled as public rates in savings context (member deals may be better — never worse-informed alerts)

---
