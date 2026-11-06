---
stage: test
bolt: 103-no-availability-is-conclusive
created: 2026-11-06T17:10:30Z
---

# Test Walkthrough

- Unit: a confident "unavailable" ends as unavailable; 0.6 confidence, "unclear" and "available"
  keep no valid observation; named rooms never trigger the question; the monitor records
  unavailable as `no_equivalent_offer` with the plain detail. Full suite 2,606 passed, 1 skipped;
  Ruff and mypy clean.
- Direct Jev probe on the captured cards: Kalipè "unavailable" 0.96 twice; AIRINN's real room
  cards "unavailable" probability 0.00 (never conclusive by mistake).
- Live replay on cloned data (kit `noavail-20261106`, daemon paused 17:03–17:08Z and restored
  healthy): Kalipè (2c711962) now `no_equivalent_offer`, Jev "unavailable" 0.94; AIRINN
  (032be4a7) unchanged, `no_equivalent_offer` room_mismatch=26.
