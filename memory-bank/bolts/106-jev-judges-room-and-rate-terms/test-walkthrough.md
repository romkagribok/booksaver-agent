---
stage: test
bolt: 106-jev-judges-room-and-rate-terms
created: 2026-11-10T01:03:30Z
---

# Test Walkthrough

- Unit: 2,555 passed, 1 skipped; ruff, mypy, AI-DLC validation clean.
- Staged live replay (kit `jevprice-20261110`, daemon paused 00:46-01:01Z, cloned data, no
  notifications): Park Plaza priced USD 364 via Jev's room match ("Deluxe Queen Bed" = "Deluxe Queen
  Bed Room", r0 at 0.84/0.82). AIRINN: Jev answered none twice (0.88/0.87); the Nov 17 page offers no
  plain Standard Double, only "Standard Double Room with Balcony", Business and Comfort rooms. Ayres
  (breakfast) USD 148, Best Western 512, Union Club 570 unchanged; Kalipè still no availability.
  Every logged meal answer matched its line ("Very good/Exceptional breakfast included in the price").
- Offline Jev wording check on 27 meal wordings (incl. French, Spanish, priced extras): first run one
  overclaim (bare "Breakfast"); after the hint 0 overclaims.
