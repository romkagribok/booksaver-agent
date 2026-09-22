# Tech Stack Standards

## Project Type

BookSaver Agent is a local-first Python daemon / CLI-style tool. It is not a hosted web app, frontend/backend split, SaaS product, or multi-tenant service.

## Current State

The story index records delivery and qualification status. The stack below follows accepted
decisions indexed in `standards/decision-index.md`.

## Runtime Stack (decided)

- **Language**: Python 3.11+ minimum, stdlib-first (ADR-003).
- **Runtime shape**: single local foreground daemon (`booksaver run`, ADR-005) with persisted
  randomized per-user daily slots and an adaptive interruptible `threading.Event` scheduler
  (ADR-029, superseding ADR-006's fixed interval), plus CLI entry points.
- **Persistence**: SQLite via stdlib `sqlite3`, one file under the user's data directory, versioned
  migrations, plus Fernet-encrypted, atomic, mode-0600 per-user Booking.com session bundles under a
  mode-0700 vault (ADRs 019 and 024). Legacy global session state is explicit migration input only.
- **Config**: `config.toml` via stdlib `tomllib`; secrets exclusively from environment variables (ADR-002).
- **Browser automation**: Playwright + bundled Chromium remains the legacy and `/connect` runtime
  (ADR-007, ADR-008). Every admitted manual and scheduled agentic price check defaults to
  exact-pinned Browser Use 0.11.13 in-process; Stagehand 4.0.1 remains an explicit adapter rollback
  and is never an automatic same-job fallback (ADR-043). Agentic inventory uses Browser Use for
  every trigger behind provider-neutral contracts and BookSaver-owned validation boundaries
  (ADR-044). An explicit `consented_users` route admits the owner and currently disclosed active
  invitees before statistical qualification without changing stored evidence (ADR-045). No
  Browserbase service, cross-run cache,
  selector learning, generated repair, or self-heal persistence is enabled.
- **Authenticated mobile web**: each check uses a fresh Android Chromium context with the exact
  booking owner's session and records authenticated/Genius provenance (ADR-025).
- **Remote authentication (opt-in)**: stdlib `http.server` application behind a Caddy TLS sidecar;
  transient headed Playwright Chromium on Xvfb, x11vnc bound to loopback, token-gated websockify,
  and noVNC ES modules (ADR-026). The signed viewer exchange selects desktop Chromium (1280x800)
  or the configured Android Chromium login profile; unknown hints default to mobile (ADR-047).
  Server-session verification and checks retain the configured mobile profile.
  Only Caddy publishes ports 80/443.
- **LLM integration**: official `anthropic` SDK with the fixed adaptive Sonnet 5/diagnostic Opus 5
  portfolio and `BOOKSAVER_LLM_API_KEY` (ADRs 009 and 031). The agentic executor permits Sonnet 5
  only for semantic and computer-use control; Opus never controls the browser. Calls share exact
  persisted USD admission/reconciliation and the existing hard job/day/time/action limits.
  Agentic Browser Use always uses the deployment owner's environment key; the owner-only Telegram
  aggregate may show that policy and boolean personal legacy-key presence, never key material
  (ADR-046).
- **Notifications**: stdlib `smtplib` (STARTTLS) for email, stdlib `urllib` against the Telegram Bot API (ADR-011); no BookSaver cloud relay.
- **Reservation authority**: authenticated Booking.com inventory is synchronized read-only;
  BookSaver reports savings but never creates or guides a rebooking workflow (ADR-027).

## Dependency Policy

Python runtime dependencies remain deliberate: `playwright`, `anthropic`, exact-pinned `stagehand`,
exact-pinned `browser-use` plus its explicit `pydantic-settings` compatibility dependency, and
`cryptography`. Production images install the exact resolved graph in `requirements.lock`. The
optional Docker remote-auth profile also uses distribution packages Xvfb/x11vnc/websockify/noVNC
and a Caddy image. Add a dependency only when stdlib cannot satisfy the need and record the decision
as an ADR (ADR-003).

## Session continuity runtime (ADR-050)

The qualified Linux deployment performs read-only session maintenance through the existing daemon
scheduler and browser gate. One ephemeral Python worker uses private socket transport, Linux
child-subreaper ownership and pidfd/start-time-bound signals so detached browser descendants are
confirmed stopped before the gate is released. It is not a second scheduler or persistent service.
Unsupported host platforms disable this background adapter without recording authentication
failures or reconnect nudges; existing foreground browser paths continue. No new package is added.
