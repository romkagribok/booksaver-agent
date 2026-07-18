---
unit: 001-interactive-command-navigation
intent: 005-telegram-command-navigation
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-18T22:14:33.000Z
updated: 2026-07-18T23:04:34Z
---

# Unit Brief: Interactive Command Navigation

## Purpose

Provide native command discovery and safe inline selection for every enumerable input required by
BookSaver's existing Telegram command surface.

## Scope

### In Scope

- Default and owner-scoped Telegram command menus.
- Prefix-based callback routing and callback access checks.
- Booking picker for `/checks` and opportunity picker for `/rebook`.
- Owner admin action, user, mode, confirmation, cancel, and back navigation.
- Typed-command compatibility and stale/forged callback handling.

### Out of Scope

- New booking edit/delete commands.
- Inline-query/autocomplete behavior while typing an argument.
- Mini Apps, web UIs, custom date pickers, or Telegram webhooks.
- Turning secret keys, invite codes, property names, dates, or prices into enumerated choices.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Publish a scoped native Telegram command menu | Must |
| FR-2 | Route callback queries through a reusable guarded router | Must |
| FR-3 | Offer scoped selection for booking and savings inputs | Must |
| FR-4 | Offer a complete owner-only admin interaction menu | Must |
| FR-5 | Render callback results after Boolean Telegram acknowledgements | Must |

## Domain Concepts

### Key Entities and Values

| Concept | Description | Relevant attributes |
|---------|-------------|---------------------|
| Command definition | Metadata Telegram displays in its native command menu | command, description, scope |
| Callback route | Registered feature namespace for a callback family | prefix, handler |
| Selection callback | Untrusted pointer to a locally stored choice | sender, chat, message, payload |
| Admin confirmation | Explicit owner decision immediately before mutation | action, target/value, confirm/cancel |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Publish commands | Synchronize default and owner command lists | known command definitions, owner chat | Telegram acknowledgement |
| Dispatch callback | Route an authorized callback by prefix | callback query | handled/stale result |
| Render picker | Convert scoped entities into compact buttons | caller identity, repository results | inline keyboard |
| Confirm admin action | Re-resolve and mutate only after owner confirmation | callback identity and selection | edited result message |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 5 |
| Must Have | 5 |
| Should Have | 0 |
| Could Have | 0 |

### Stories

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-043 | Discover applicable commands natively | Must | Complete |
| US-044 | Route and authorize interactive callbacks | Must | Complete |
| US-045 | Select bookings and savings opportunities | Must | Complete |
| US-046 | Navigate owner administration safely | Must | Complete |
| US-047 | Handle Boolean Telegram action results | Must | Complete |

## Dependencies

### Depends On

| Capability | Reason |
|------------|--------|
| Intent 003 Telegram bot gateway | Existing long poll, command router, client, and dialogs |
| Intent 003 user access and keys | Current owner/invite authorization and scoped repositories |
| Intent 003 Telegram rebook gate | Existing callback confirmations and guided workflow |

### Depended By

| Consumer | Reason |
|----------|--------|
| VPS Telegram UX | Uses command menu and pickers after image rebuild |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Telegram Bot API | Command metadata and inline callback transport | Low/medium: network failure must degrade safely |

## Technical Context

### Suggested Technology

Use the existing Python 3.11 stdlib Telegram client, typed router/dataclass patterns, SQLite
repositories, callback data prefixes, pytest fakes, Ruff, and mypy. Add no dependency or schema.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Gateway → Telegram Bot API | Outbound client | HTTPS JSON |
| BotLoop → CallbackRouter | In-process | Typed Python calls |
| Picker handlers → repositories | In-process | SQLite adapters |
| Picker handlers → existing operations | In-process | Existing command/rebook services |

### Data Storage

No new durable data. Callback payloads are transient, and every entity is reloaded from SQLite.

## Constraints

- Keep every callback payload at or below 64 UTF-8 bytes.
- Never infer ownership from callback data or a previously rendered keyboard.
- Always acknowledge callback queries, including denied, stale, and unknown inputs.
- Existing rebook and admin safety rules remain authoritative.

## Success Criteria

### Functional

- [ ] Telegram shows applicable command names and descriptions.
- [ ] `/checks`, `/rebook`, and `/admin` need no typed identifier/subcommand in normal use.
- [ ] Typed arguments remain accepted.

### Non-Functional

- [ ] Every callback path is authorized and acknowledged.
- [ ] Command-menu API failures do not stop the bot.
- [ ] No new dependency, schema, process, or service.

### Quality

- [ ] Focused and full pytest suites pass.
- [ ] Ruff and mypy pass.
- [ ] AI-DLC artifacts and story index remain consistent.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `016-interactive-command-navigation` | Simple Construction | US-043–US-046 | Deliver scoped command discovery and interactive current-command inputs |
| `018-interactive-command-navigation` | Simple Construction | US-047 | Correct Boolean action responses and callback rendering isolation |

## Notes

The product owner authorized autonomous progression through inception and simple-bolt stages, with a
single compressed validation immediately before official bolt completion.
