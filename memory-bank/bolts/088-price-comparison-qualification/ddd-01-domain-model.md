---
stage: domain-model
bolt: 088-price-comparison-qualification
created: "2026-10-10T01:48:50Z"
status: complete
---

# Release qualification and activation — domain model

- **Gate A (pre-release)**: the full test, lint and type gates; exact-image smoke; a stage probe on a
  production database snapshot with no network and nothing delivered; reviewed pull request.
- **Gate B (live)**: native Telegram reports for a manual owner check and for scheduled checks of
  the owner and an invitee, with costs and results matching the stored records.
- **ActivationProfile**: `[jev_comparison] enabled`, `participants`, daily cap, the TypeSafe key.
- **Kill switch**: `enabled = false` (or selecting another price executor) plus a restart; pending
  arms are closed as interrupted and history is kept.
