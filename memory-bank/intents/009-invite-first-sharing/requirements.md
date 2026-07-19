---
intent: 009-invite-first-sharing
phase: inception
status: complete
created: 2026-07-19T02:29:55Z
updated: 2026-07-19T14:48:51Z
---

# Requirements: Invite-First Sharing

## Intent Overview

Make sharing an owner-operated BookSaver Telegram bot understandable and safe: the owner can hand off
one copyable invite command, recognize admitted users by their current Telegram username, rely on
invite admission as the only non-owner access posture, and ensure revoked users receive an explicit
access-loss message. The owner role and owner-only administration remain; only the obsolete
owner-only *admission mode* is removed.

## Functional Requirements

### FR-1: Deliver a copyable invite command

- **Description**: Creating an invite must send guidance and the exact redemption command as two
  separate Telegram messages so the second bubble can be copied without selecting surrounding prose.
- **Acceptance Criteria**:
  - Typed `/admin invite` and the inline **Create invite** action each create one single-use code.
  - The first response explains that the next message should be forwarded or copied and contains no
    bearer invite code.
  - The second response is exactly `/start <code>` with no prefix, suffix, Markdown decoration, or
    unrelated text.
  - The separated command redeems the same stored code and remains single-use.
  - Callback-based creation edits/acknowledges the admin menu and sends the command as a new message;
    it does not overwrite the copyable command through a second edit.
  - If the exact-command message fails to send, exactly one code remains stored and unused, the
    failure is logged without the code, and the owner may explicitly create a new invite; no implicit
    retry creates a second code or duplicate message.
- **Priority**: Must
- **Related Stories**: US-062

### FR-2: Maintain recognizable Telegram usernames

- **Description**: After successful owner authorization or invite redemption, persist the sender's
  latest optional Telegram username as display metadata while continuing to authorize exclusively by
  Telegram's stable numeric user ID.
- **Acceptance Criteria**:
  - Message and callback updates carry Telegram's optional `from.username` into the access boundary.
  - Successful owner linkage, invite redemption, and later active-user interactions create or refresh
    the stored username; removing a Telegram username clears the stored display metadata.
  - Usernames are normalized without a leading `@` and written only when the stored value changes.
  - Unknown users, invalid-code attempts, and revoked-user traffic never create or refresh username
    data.
  - `/admin users` and revoke/purge pickers prefer `@username` and otherwise show a non-sensitive
    fallback such as `User #N (no @username)` rather than a Telegram chat ID.
  - Usernames are optional, mutable, non-unique metadata and are never used as an authorization key.
- **Priority**: Must
- **Related Stories**: US-063

### FR-3: Enforce invite-only non-owner admission

- **Description**: The owner is always admitted and remains the sole administrator. Every non-owner
  must be an active known user or redeem a valid single-use invite; there is no runtime/configurable
  owner-only admission mode.
- **Acceptance Criteria**:
  - A stranger without a valid invite is refused; a valid unused invite admits exactly one user.
  - Known active invited users remain admitted across daemon restarts.
  - The `/admin mode` command, inline mode menu, and runtime mode mutator are removed.
  - Production access control contains no owner/invite behavior branch: invite-only admission is an
    invariant, not merely a default.
  - Legacy `access_mode = "owner"` or `"invite"` configuration cannot restore owner-only behavior and
    is handled compatibly during upgrade: missing, `"owner"`, and `"invite"` all normalize to the
    fixed invite-only policy; `"open"`, `"public"`, and unknown values remain invalid.
  - Documentation and generated config describe a private invite-only bot, never a public bot, and
    newly generated config omits the legacy setting.
- **Priority**: Must
- **Related Stories**: US-064

### FR-4: Explain revocation immediately and on later interaction

- **Description**: A user whose access is revoked must receive the exact message `You no longer have
  access to this bot.` immediately after successful revocation and when attempting later commands or
  callbacks.
- **Acceptance Criteria**:
  - Revocation commits before notification; notification failure cannot undo the revoked state.
  - When a Telegram identity is available, the bot makes one immediate best-effort delivery attempt
    after commit. This security-state notice is not silently dropped by the generic outbound message
    limiter; Telegram API failure is caught and logged.
  - The owner receives a separate administrative confirmation which accurately distinguishes a
    successful target delivery from a failed/unavailable delivery.
  - The first eligible later revoked-user command in each refusal window receives the exact message;
    additional commands may be silently rate-limited. Every callback is acknowledged with the same
    explanation.
  - Unknown users and invalid/expired/used invite attempts retain a generic private-bot refusal and
    cannot distinguish stored access states.
- Existing refusal limits continue to prevent reply abuse; the one-time admin-triggered revoke notice
  bypasses only the generic outbound limiter and never bypasses Telegram API error handling.
- **Priority**: Must
- **Related Stories**: US-065

### FR-5: Preserve owner administration and sharing safety

- **Description**: Improve sharing without making the bot public, weakening user scoping, changing
  billing/key isolation, or exposing invite/identity data outside the owner boundary.
- **Acceptance Criteria**:
  - `/admin`, invite creation, user listing, revoke, and purge remain owner-only.
  - Invite codes remain unguessable, single-use bearer secrets and are not logged.
  - Telegram usernames appear only in owner administration, never user-facing lists, check traces, or
    application logs.
  - Purge removes the username with the user row; revoke retains it consistently with the existing
    retained-data policy.
  - Invited-user booking/check/LLM limits and optional encrypted personal-key behavior are unchanged.
- **Priority**: Must
- **Related Stories**: US-066

## Non-Functional Requirements

### Privacy and Security

- Numeric Telegram user ID remains the only external identity used for authorization.
- Username collection begins only after successful authorization/redemption and is limited to the
  optional current handle required for owner recognition.
- Invite validity and user state are not disclosed to unknown senders.

### Reliability and Compatibility

- Schema migration from v8 to v9 is additive, idempotent, and preserves users, keys, bookings, checks,
  savings, and invite records.
- Existing deployed configs containing `access_mode = "owner"` must start safely in the new fixed
  invite-only posture rather than crash-loop or retain owner-only admission.
- Telegram API failures during the second invite message or revoke notification are logged and do not
  corrupt invite/revocation persistence.

### Verification

- Fresh-schema and v8→v9 migration tests, access-control tests, Telegram update/gateway tests, admin
  command tests, Ruff, mypy, full pytest, and AI-DLC validation must pass.

## Constraints

- Keep the stdlib Telegram client and existing single-process gateway; add no runtime dependency.
- Do not add public/open bot access or username-based authentication.
- Do not rewrite completed historical artifacts; supersede dual-mode behavior through this intent and
  a new ADR during construction.

## Assumptions and Decisions

- "Always invite" means removing owner-only *admission mode*, not removing the owner role or making
  administration available to invited users.
- `@username` is preferred when Telegram supplies it. Users without a username remain manageable
  through inline pickers and an internal BookSaver user-number fallback; Telegram chat IDs are not
  shown in normal admin output.
- The product owner authorized continuous Inception and Construction through the final Test
  checkpoint, then approved the combined final review and closure.

## Scope Exclusions

- Public signup, reusable invite links, role delegation, user-to-user discovery, group-chat support,
  or username-based authorization.
- Collecting full Telegram profile names, phone numbers, bios, or other profile data.
