---
intent: 005-telegram-command-navigation
phase: inception
status: complete
created: 2026-07-18T22:14:33.000Z
updated: 2026-07-18T23:04:34Z
---

# Requirements: Telegram Command Navigation

## Intent Overview

Make BookSaver's Telegram interface discoverable and selectable instead of requiring users to
remember command names, booking UUIDs, savings-opportunity UUIDs, or admin subcommand syntax. Native
Telegram command suggestions will expose the command surface; commands whose inputs come from
BookSaver's own data will reply with user-scoped inline keyboards.

Telegram does not provide native autocomplete for command arguments. This intent therefore combines
`setMyCommands` command discovery with inline selection after `/checks`, `/rebook`, and `/admin` are
sent. Typed command arguments remain supported for operators and backward compatibility.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Make commands discoverable | Typing `/` or opening Telegram's command menu shows every applicable BookSaver command | Must |
| Remove identifier copying | `/checks` and `/rebook` can be completed by tapping a user-owned item | Must |
| Make owner administration navigable | `/admin` exposes actions, applicable users, choices, and confirmations as buttons | Must |
| Preserve safety and power-user paths | Callback and typed flows enforce identical scoping, authorization, and destructive-action gates | Must |

## Functional Requirements

### FR-1: Publish a scoped native Telegram command menu

- **Description**: On bot startup, BookSaver must publish its supported commands through Telegram's
  `setMyCommands` API. The default private-chat list must omit owner-only administration; the owner
  chat scope must include `/admin`.
- **Acceptance Criteria**:
  - The published descriptions match the implemented command surface and `/help`.
  - The owner receives a chat-scoped command list containing `/admin`; ordinary private chats do not.
  - A Telegram failure while publishing commands is logged and does not prevent the daemon or bot
    update loop from starting.
  - No bot token, chat secret, or user data is logged.
- **Priority**: Must
- **Related Stories**: US-043

### FR-2: Route callback queries through a reusable guarded router

- **Description**: Replace the single-purpose rebook callback seam with a prefix-based router that
  lets command features register independent handlers without weakening callback authorization.
- **Acceptance Criteria**:
  - Distinct `checks:`, `rebook:`, and `admin:` callback families route to their registered handler.
  - Duplicate prefixes are rejected during wiring and unknown/stale callbacks are acknowledged with
    a neutral expiry message rather than leaving Telegram's spinner active.
  - Every callback is re-authorized using its sender/chat identity before feature code runs.
  - Existing rebook confirmation callbacks retain their chat/user/nonce validation and shutdown-safe
    behavior.
- **Priority**: Must
- **Related Stories**: US-044

### FR-3: Offer scoped selection for booking and savings inputs

- **Description**: When `/checks` or `/rebook` is sent without an identifier, BookSaver must render
  tappable choices derived only from the caller's own stored data. Selecting a choice must execute the
  same operation as the existing typed command.
- **Acceptance Criteria**:
  - `/checks` without arguments lists the caller's bookings with recognizable property/date labels;
    a tap renders that booking's recent check history.
  - `/rebook` without arguments lists only the caller's actionable savings opportunities; a tap starts
    the existing guided rebook workflow.
  - Callback payloads stay within Telegram's size limit and never trust a displayed label as an ID.
  - A forged, stale, cross-user, or deleted selection returns the same non-disclosing not-found result
    as the typed command and performs no protected action.
  - Existing `/checks <id>` and `/rebook <id>` behavior remains supported.
- **Priority**: Must
- **Related Stories**: US-045

### FR-4: Offer a complete owner-only admin interaction menu

- **Description**: `/admin` without arguments must render owner-only action buttons. Actions that
  require a target or choice must render eligible values, and mutating actions must use explicit
  confirmation buttons before execution.
- **Acceptance Criteria**:
  - The menu exposes users, create invite, revoke user, purge user, and access mode.
  - Revoke and purge target lists exclude the owner; callbacks re-resolve the selected user at action
    time and refuse stale/owner targets.
  - Revoke, purge, and access-mode changes require an explicit Confirm tap with a Cancel path.
  - Purge retains its existing cascade semantics; invite generation and users listing retain their
    existing behavior.
  - Non-owner callbacks cannot disclose user lists or mutate access state, including in invite mode.
  - Existing typed `/admin ...` syntax remains supported.
- **Priority**: Must
- **Related Stories**: US-046

### FR-5: Render callback results after Boolean Telegram acknowledgements

- **Description**: Telegram action endpoints that return Boolean success must not be treated as
  message objects, and callback acknowledgement must not suppress result rendering or valid scoped
  operation dispatch.
- **Acceptance Criteria**:
  - Boolean success from `answerCallbackQuery` and `deleteMessage` is returned without conversion.
  - Checks rendering is attempted independently from callback acknowledgement.
  - Rebook selection continues into its existing ownership check independently from callback UI
    update failures.
  - Callback acknowledgement/edit failures are logged and contained.
- **Priority**: Must
- **Related Stories**: US-047

## Non-Functional Requirements

### Security and Privacy

| Requirement | Metric | Target |
|-------------|--------|--------|
| Callback authorization | Protected callbacks rechecked against current access and ownership | 100% |
| Cross-user disclosure/action | Foreign booking, opportunity, or admin data exposed or acted on | 0 |
| Destructive confirmation | UI purge/revoke/mode mutations without explicit confirmation | 0 |

### Reliability and Compatibility

| Requirement | Metric | Target |
|-------------|--------|--------|
| Command-menu degradation | Bot startup failures caused by `setMyCommands` failure | 0 |
| Callback acknowledgement | Routed, refused, stale, and unknown callbacks acknowledged | 100% |
| Typed compatibility | Existing argument-bearing command tests retained | 100% |
| Quality gates | Full pytest, Ruff, and mypy | Clean |

### Usability

| Requirement | Metric | Target |
|-------------|--------|--------|
| Identifier-free checks/rebook | Required UUID typing for normal selection flow | 0 |
| Admin navigation | Required subcommand/target typing for normal owner flow | 0 |
| Choice labels | Booking/opportunity choices recognizable without UUID lookup | Property/date or savings context on every choice |

## Constraints

### Technical Constraints

- Use the existing stdlib Telegram client, SQLite repositories, long-poll loop, rate limits, and
  inline-keyboard mechanisms; add no runtime dependency.
- Telegram callback data is untrusted and limited to 64 bytes; resolve authoritative state from
  SQLite after every selection.
- Keep callback routing in the Telegram inbound-adapter boundary and domain/persistence rules in
  their existing modules.

### Business Constraints

- Owner/invite access modes remain the only supported modes.
- No callback may create autonomous Booking.com reservation, payment, or cancellation authority.

## Assumptions

| Assumption | Risk if Invalid | Mitigation |
|------------|-----------------|------------|
| Telegram clients display commands registered through `setMyCommands` | Some clients may cache an older list | Republish on every bot startup and retain `/help` |
| A user has a small number of bookings/opportunities | A keyboard could become long | Existing per-user booking limit is three; cap opportunity choices and retain typed input |
| Telegram callbacks can arrive late or be replayed | A stale button could target changed data | Re-authorize and reload every selected entity at callback time |

## Open Questions

| Question | Owner | Resolution |
|----------|-------|------------|
| Should argument suggestions appear while typing? | Telegram platform | Resolved: native commands autocomplete names only; use post-command inline keyboards |
| Should edit/delete booking commands be added here? | Product owner | Resolved: out of scope; this intent improves navigation of the current command surface |
| Which dialog inputs remain free-form? | Product owner / security | Secrets, invite codes, property/date/price text, and other values not safely enumerable remain dialog text |

## Requirement Quality Checklist

- [x] All requirements are testable.
- [x] Acceptance criteria are binary.
- [x] Intent-specific NFRs have measurable targets.
- [x] Dependencies and constraints are identified.
- [x] Assumptions and mitigations are stated.
- [x] Checkpoints 1 and 2 are covered by the product owner's explicit command-intent direction and
  continuous-flow authorization on 2026-07-18.
