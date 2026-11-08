---
stage: test
bolt: 104-jev-reads-room-type
created: 2026-11-08T02:39:22Z
---

# Test Walkthrough

- Unit: agreed room read; disagreeing or 0.4 room stays unknown; multi-room or unknown party is not
  asked; an agreed total at 0.51/0.54 counts; an agreed component line is still rejected; meals read
  after "Private suite / Deluxe Queen Bed"; room-mismatch wording. Full suite 2,616 passed, 1
  skipped; Ruff and mypy clean.
- Diagnosis replay (kit `parkplaza-20261107`): Park Plaza total chosen by both calls at 0.51/0.54;
  room parser found nothing.
- Candidate replay of users 4 and 1 on cloned data (kit `jevroom-20261108`, daemon paused and
  restored healthy, last at 02:38:58Z): Park Plaza became eligible (Deluxe Queen Bed, USD 344.50,
  refundable until 2026-11-12, meals none); the other seven upcoming reservations unchanged; Jev's two
  room answers agreed on every page (confidence 0.51 to 0.71). Wording comparison on Park Plaza's
  lines: chosen wording "Deluxe Queen Bed" 0.76/0.80.
