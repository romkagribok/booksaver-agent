---
bolt: 036-synchronized-booking-interface
completed: 2026-07-27T17:02:34Z
---

# Test Report

- Telegram command publication replaces the default, all-private-chat, and owner-chat menus so
  retired booking mutation commands disappear from every Telegram scope after restart.
- Trigger order, authenticated inventory projection, async admission, caller isolation, full
  inventory rendering, eligibility reasons, unknown retired commands, and command catalog behavior
  are covered.
- CLI help confirms only `init`, `config`, `run`, scoped `auth`, `stop`, read-only `bookings`,
  `checks`, and `savings` surfaces.
- Full repository: **962 passed in 13.06s**.
- Ruff: clean. Mypy across 97 source files: clean.
- Live Booking.com inventory and Telegram scoped-menu validation passed on the VPS.
