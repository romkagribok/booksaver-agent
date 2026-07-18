---
stage: implement
bolt: 016-interactive-command-navigation
created: 2026-07-18T22:28:16Z
---

## Implementation Walkthrough: Interactive Command Navigation

### Summary

BookSaver now publishes applicable commands to Telegram and turns stored booking, savings, and admin
choices into guarded inline-keyboard interactions. Existing typed commands, user scoping, owner
authorization, rebook confirmation gates, and admin persistence operations remain the execution
authority behind the new navigation layer.

### Structure Overview

An authoritative command catalog feeds help and Telegram metadata. A reusable prefix router shares
the existing callback-query transport among checks, rebook, and admin feature families. Gateway wiring
performs callback access checks before dispatch; each feature then reloads and validates its selected
entity immediately before use.

### Completed Work

- [x] `src/booksaver/infrastructure/telegram/command_catalog.py` - Defines one command catalog for
  owner/default Telegram scopes and help rendering.
- [x] `src/booksaver/infrastructure/telegram/client.py` - Publishes scoped commands through the
  existing stdlib Telegram API seam.
- [x] `src/booksaver/infrastructure/telegram/router.py` - Routes independent callback namespaces and
  rejects ambiguous duplicate wiring.
- [x] `src/booksaver/infrastructure/telegram/gateway.py` - Synchronizes command menus nonfatally,
  applies callback access checks, acknowledges unknown/refused callbacks, and wires all feature
  families through the shared rate-limited sender.
- [x] `src/booksaver/infrastructure/telegram/commands_readonly.py` - Shows scoped help and a caller-
  owned booking picker whose selection renders the existing recent-check output.
- [x] `src/booksaver/infrastructure/telegram/rebook_gate.py` - Shows caller-owned savings choices and
  feeds a selected opportunity into the existing guided session and confirmation machinery.
- [x] `src/booksaver/infrastructure/telegram/admin_commands.py` - Adds owner action, target, mode,
  confirmation, cancel, and back navigation while retaining typed administration.
- [x] `tests/unit/telegram/` - Covers command scopes, publication degradation, callback routing and
  authorization, picker ownership, guided-session selection, admin confirmations, stale callbacks,
  typed compatibility, and client payloads.

### Key Decisions

- **Post-command selection**: Telegram's native menu discovers command names; inline keyboards supply
  live application-owned inputs after the command is sent.
- **Authoritative reload**: Callback labels are presentation only. UUID/user selections are reloaded
  from SQLite and rechecked against the current sender at action time.
- **One guarded callback boundary**: Access control runs before prefix dispatch, while checks/rebook
  ownership and owner-only admin checks remain defense in depth inside handlers.
- **UI mutations confirm**: Revoke, purge, and access-mode changes require Confirm in the new menu;
  Cancel returns to the admin menu without mutation.
- **Nonfatal discovery**: Command metadata publication is convenience, so Telegram errors cannot keep
  the long-poll bot from starting.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

Typed `/checks <id>`, `/rebook <id>`, and `/admin ...` calls remain supported. Free-form registration,
personal-key, and invite-code inputs intentionally remain in their existing secure dialogs.
