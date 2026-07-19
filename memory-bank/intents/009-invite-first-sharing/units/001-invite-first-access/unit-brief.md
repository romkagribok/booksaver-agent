---
unit: 001-invite-first-access
intent: 009-invite-first-sharing
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-19T02:34:21Z
updated: 2026-07-19T14:48:51Z
---

# Unit Brief: Invite-First Access

## Purpose

Make an owner-operated BookSaver bot easy to share with trusted people while enforcing private,
invite-only non-owner admission and making every revocation clear without weakening privacy.

## Scope

### In Scope

- Separate invite guidance from the exact copyable redemption command.
- Capture, persist, refresh, clear, and owner-display optional Telegram usernames.
- Remove configurable/runtime owner-only admission mode while retaining the owner role.
- Notify revoked users immediately when possible and explain later refused commands/callbacks.
- Preserve invite secrecy, stable-ID authorization, user scoping, limits, and encrypted-key behavior.

### Out of Scope

- Public signup, reusable invite links, delegated administration, or username authentication.
- Full Telegram names, phone numbers, bios, group-chat support, or user discovery.
- Changes to bookings, checks, savings, quotas, LLM billing, or guided rebooking.
- Admin access to user booking/check details; that privacy boundary belongs to Intent 010.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Deliver a copyable invite command | Must |
| FR-2 | Maintain recognizable Telegram usernames | Must |
| FR-3 | Enforce invite-only non-owner admission | Must |
| FR-4 | Explain revocation immediately and on later interaction | Must |
| FR-5 | Preserve owner administration and sharing safety | Must |

## Domain Concepts

### Key Entities

| Entity | Description | Attributes |
|--------|-------------|------------|
| User | Authorized owner or invited user | Internal ID, stable Telegram ID, optional username, role, access state |
| InviteCode | Single-use bearer credential issued by the owner | Code, issuer, timestamps, used-by identity |
| TelegramIdentity | Sender metadata observed on an update | Stable numeric ID, optional mutable username |
| AccessDecision | Admission result without stranger-state disclosure | Allowed, revoked, or generic refusal |

### Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Issue invite | Persist one code and deliver a two-message handoff | Owner command/callback | Guidance plus exact `/start <code>` |
| Authorize sender | Admit owner, active user, or valid invite redemption | Stable ID, username, command | Authorized identity or refusal category |
| Refresh username | Persist latest optional handle after authorization | User ID, optional username | Updated display metadata |
| Revoke access | Commit revoked state then notify user and owner | Internal user ID | Revoked user plus delivery result |
| Render user label | Display identity only inside owner administration | User record | `@username` or internal-number fallback |

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
| US-062 | Deliver copyable invite command | Must | Complete |
| US-063 | Maintain recognizable usernames | Must | Complete |
| US-064 | Enforce invite-only admission | Must | Complete |
| US-065 | Explain revoked access | Must | Complete |
| US-066 | Preserve sharing safety | Must | Complete |

## Dependencies

### Depends On

| Unit | Reason |
|------|--------|
| `002-user-access-and-keys` (Intent 003) | Existing user, invite, access, encrypted-key, and admin foundations |
| `001-interactive-command-navigation` (Intent 005) | Existing callback router and confirmed admin pickers |

### Depended By

| Unit | Reason |
|------|--------|
| None | This unit refines the existing Telegram access surface in place |

### External Dependencies

| System | Purpose | Risk |
|--------|---------|------|
| Telegram Bot API | Sender identity and outbound invite/revocation messages | Medium: optional fields and delivery failure |
| SQLite | Durable identity, access state, and invite persistence | Low: additive migration with preservation requirements |

## Technical Context

### Suggested Technology

Extend the existing Python 3.11 stdlib Telegram client, synchronous access boundary, dataclass domain
types, and SQLite migration framework. Add no dependency and no parallel gateway path.

### Integration Points

| Integration | Type | Protocol |
|-------------|------|----------|
| Telegram update loop | Inbound API | Telegram Bot API JSON over HTTPS |
| Access control | Application boundary | In-process typed command/callback identity |
| User repository | Persistence | SQLite transaction |
| Admin commands | Owner UI | Telegram commands and inline callbacks |

### Data Storage

| Data | Type | Volume | Retention |
|------|------|--------|-----------|
| Optional Telegram username | Nullable SQLite text | One current value per user | Until changed, cleared, or purged |
| Invite code | Existing SQLite record | Small owner-issued set | Existing single-use policy |
| Revoked access state | Existing SQLite enum | One value per user | Retained until purge |

## Constraints

- Authorize only by stable numeric Telegram user ID, never username.
- Do not persist username data for unknown, invalid-code, or revoked traffic.
- Commit invite/revocation state before outbound delivery; delivery failures cannot roll back state.
- Do not reveal Telegram IDs in normal admin labels when a safe internal fallback is available.
- Keep public/open modes invalid and treat legacy private mode values as compatibility input only.

## Success Criteria

### Functional

- [x] Both invite entry points emit guidance then an exact separate redemption command.
- [x] Owner administration recognizes users by current username or internal fallback.
- [x] Every non-owner admission uses active membership or a valid single-use invite.
- [x] Revoked users receive the exact access-loss message proactively and on later interaction.
- [x] Owner-only administration and all existing per-user boundaries remain enforced.

### Non-Functional

- [x] Fresh schema v9 and v8-to-v9 migration preserve all existing data.
- [x] Legacy deployed private access-mode config starts in fixed invite-first posture.
- [x] Telegram delivery failures are isolated from durable invite/revoke state.

### Quality

- [x] Focused and full automated tests pass.
- [x] Ruff and mypy pass.
- [x] All acceptance criteria pass; AI-DLC validation has no new issues beyond 38 historical findings.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| `021-invite-first-access` | Simple Construction | US-062–US-066 | Deliver the cohesive sharing, identity, admission, revocation, and safety correction |

## Notes

The fixed invite posture supersedes Bolt 009's dual owner/invite admission modes; construction must
record that architectural change in a new ADR without rewriting the completed historical ADR.
