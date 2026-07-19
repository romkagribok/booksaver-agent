# ADR-022: Fixed invite-first admission for non-owner Telegram users

- **Status**: accepted
- **Date**: 2026-07-19T02:39:40Z
- **Bolt**: 021-invite-first-access (invite-first-access)
- **Supersedes**: Bolt 009's runtime `owner`/`invite` admission-mode choice

## Context

BookSaver's Telegram gateway originally supported two private modes: owner-only and invite. In an
owner-operated bot intended to be shared, this runtime/config choice makes a valid invite appear
broken whenever the daemon still uses the historical `owner` value, adds an unnecessary mutable admin
control, and produces two private refusal states that users and operators cannot diagnose cleanly.

The owner role, owner-only administration, single-use invite codes, stable numeric Telegram identity,
and prohibition on public access remain necessary. Only the switch between two non-public admission
postures is unnecessary.

## Decision

1. The owner remains always admitted and is the only administrator.
2. A non-owner is admitted only when already active or when atomically redeeming one valid unused
   invite. There is no production behavior branch for owner-only versus invite mode.
3. `/admin mode`, its callback menu, and the runtime mode mutator are removed.
4. For safe deployed-config migration, the loader still inspects the legacy key: absent, `owner`, and
   `invite` normalize to the fixed invite-first posture. `open`, `public`, and unknown values remain
   invalid. Newly generated config omits the key.
5. Telegram's stable numeric user ID remains the authorization identity. Optional usernames are
   mutable owner-visible labels collected only after successful authorization and never affect access.
6. Unknown and unusable-invite traffic retains one generic refusal. Revoked users are distinguished
   internally only to provide the explicit access-loss message.

## Alternatives considered

- **Keep both modes but default to invite**: still permits deployed/runtime state to make valid invites
  appear broken and retains an unnecessary policy branch. Rejected.
- **Remove all parsing of `access_mode`**: silently ignoring `open` or arbitrary values would weaken
  validation and make upgrades ambiguous. Rejected.
- **Make the bot public**: violates the self-hosted private-bot boundary and cost controls. Rejected.
- **Authorize by username**: handles are optional, mutable, and recyclable. Rejected.

## Consequences

- Sharing has one predictable flow: issue invite, forward exact `/start <code>`, redeem once.
- Existing VPS configs with `access_mode = "owner"` start safely and valid invites work without manual
  config repair; the obsolete key can be removed later.
- Public/open configurations still fail closed.
- The owner role and all existing user-data, encrypted-key, quota, alert, and rebook boundaries remain.
- Current documentation must say invite-only; historical Bolt 009 artifacts remain unchanged.
