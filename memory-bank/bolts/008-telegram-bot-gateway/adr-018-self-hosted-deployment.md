# ADR-018: Amend "local-only" to "self-hosted, owner-operated" (laptop or VPS)

- **Status**: accepted (validated with the user at Checkpoint 1, 2026-07-11)
- **Date**: 2026-07-11
- **Bolt**: 008-telegram-bot-gateway (telegram-bot-gateway)

## Context

The MVP requirements (`US-013`, intent 001) and every ADR up to this point describe
BookSaver as strictly local: "all credentials, sessions, and data on the user's machine,"
no hosted service, no distributed components. Intent 003 makes a Telegram bot the primary
interface and runs the daemon unattended so it can answer chats and run scheduled checks
without a laptop needing to stay powered on and network-reachable 24/7 — the natural home
for that is a small VPS the user (or the bot's operator, "owner") controls, not their
personal laptop.

This is a genuine scope question, not just an implementation detail: does moving the
daemon off the user's own laptop violate the "local-only, no hosted service" product
constraint that the whole project's trust model rests on? The distinction that matters to
users is *who operates the infrastructure and who else's data touches it* — not *which box
the process happens to run on*.

## Decision

Amend the MVP's "local-only" wording to **"self-hosted, owner-operated"**:

- BookSaver may run on the user's own laptop **or** on a VPS the same user (the "owner")
  rents and administers. Either way, "local" now means "on infrastructure the operator
  controls," not literally "on the laptop next to the user."
- What does **not** change: there is still no BookSaver-hosted cloud backend of any kind —
  nothing phones home to a service operated by this project. No third-party data sharing.
  Credentials, sessions, and the SQLite database live only on the operator's own machine
  (laptop or VPS), never on infrastructure this project runs on the user's behalf.
- Laptop single-user mode is unaffected and remains fully supported — it is simply the
  degenerate case of "owner-operated infrastructure" where the owner's own laptop is the
  server. Nothing in intent 003 requires a VPS; `[telegram_bot]` is opt-in (US-023) and
  every prior CLI-only workflow keeps working unchanged.
- The bot itself stays **owner/invite access only** (FR-2, Checkpoint 1) — never public —
  which keeps the "who else's data touches this" answer narrow even on a shared VPS: only
  people the owner explicitly invites, still isolated per-user at the repository layer
  (unit 002, later bolt).

## Alternatives considered

- **Keep "local-only" literal (laptop only), block VPS deployment**: rejected — it would
  make the Telegram-as-main-interface goal (FR-1) unattainable, since a Telegram bot only
  a laptop can answer defeats "run unattended for days" (a Checkpoint-1 business goal).
- **Silently reinterpret "local" without an ADR**: rejected — the local-only constraint is
  load-bearing for user trust (no data leaves infrastructure the user controls) and is
  referenced by name in CLAUDE.md and multiple prior ADRs; a scope change to it needs to be
  explicit and reviewable, hence this ADR plus the Checkpoint-1 validation.
- **Require the VPS to be BookSaver-project-operated (a real hosted backend)**: rejected —
  this is exactly the "operator of a scraping service for third parties" posture the intent
  requirements already rule out (FR-2 rationale); would also reintroduce the multi-tenant
  SaaS model the project explicitly disclaims.

## Consequences

- CLAUDE.md and the intent 003 requirements already use "self-hosted, owner-operated"
  language; this ADR is the formal record superseding the literal "local-only" wording of
  `US-013` for deployments that opt into `[telegram_bot]` or a VPS.
- Deployment docs (unit 005, bolt 012 — Dockerfile/systemd, ops runbook) must keep making
  the distinction concrete: "your VPS, your credentials, your data" — not a hosted product.
- Every future feature must keep satisfying "no BookSaver-hosted backend, no third-party
  data sharing" regardless of which physical machine the operator chooses to run on; this
  ADR does not open the door to any hosted/managed offering.
- Session strategy on a display-less VPS (logged-out checks by default, optional cookie
  import) is a separate, later decision (unit 005) — this ADR only settles the deployment
  *location* question, not *how* the browser authenticates there.
