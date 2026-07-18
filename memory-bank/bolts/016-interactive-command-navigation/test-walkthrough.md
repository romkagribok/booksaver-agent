---
stage: test
bolt: 016-interactive-command-navigation
created: 2026-07-18T22:30:55Z
---

## Test Report: Interactive Telegram Command Navigation

### Summary

- **Focused Telegram tests**: 170/170 passed
- **Full tests**: 665/665 passed
- **Ruff**: clean across `src/` and `tests/`
- **Mypy**: clean across 73 source files
- **Diff hygiene**: `git diff --check` passed
- **Dependencies/schema**: unchanged
- **AI-DLC artifact delta**: no new validator issue; repository baseline remains 38 legacy issues

### Acceptance Criteria Validation

- ✅ **Native discovery**: One catalog supplies `/help` and `setMyCommands`; ordinary private-chat
  scope omits `/admin`, while the owner chat scope includes it.
- ✅ **Nonfatal publication**: A rejected command-menu publication is logged and long polling still
  starts.
- ✅ **Guarded callback routing**: Most-specific registered prefixes dispatch once, duplicate/empty
  prefixes fail during wiring, and access control runs before feature handlers.
- ✅ **Callback acknowledgement**: Routed, denied, malformed, stale, and unknown callback paths stop
  Telegram's client spinner without exposing protected state.
- ✅ **Booking selection**: `/checks` lists only caller-owned bookings with property/date labels;
  selection reloads ownership and renders the existing history operation.
- ✅ **Savings selection**: `/rebook` lists only caller-owned opportunities with property/savings
  labels; selection reloads ownership and enters the existing nonce-bound guided session.
- ✅ **Owner administration**: `/admin` exposes users, invite, revoke, purge, and access-mode actions;
  owner checks remain inside callbacks, non-owner targets are reloaded, and revoke/purge/mode require
  explicit confirmation with a cancel route.
- ✅ **Compatibility and safety**: Typed commands remain covered, existing rebook nonce/chat/user
  validation remains intact, callback payloads stay below 64 bytes, and no autonomous Booking.com
  authority was added.

### Regression Files

- `tests/unit/telegram/test_command_catalog.py`
- `tests/unit/telegram/test_client.py`
- `tests/unit/telegram/test_router.py`
- `tests/unit/telegram/test_gateway.py`
- `tests/unit/telegram/test_commands_readonly.py`
- `tests/unit/telegram/test_rebook_gate.py`
- `tests/unit/telegram/test_admin_commands.py`
- Full configured pytest suite, including persistence, access control, dialogs, monitoring, savings,
  and the guided-rebook confirmation state machine.

### Commands and Results

```text
python3 -m ruff check src/ tests/
All checks passed!

python3 -m mypy src/
Success: no issues found in 73 source files

python3 -m pytest tests/unit/telegram -q
170 passed in 2.26s

python3 -m pytest -q
665 passed in 5.29s

git diff --check
passed

node .specsmd/aidlc/scripts/artifact-validator.cjs
38 pre-existing repository issues; none references Intent 005 or Bolt 016

node .specsmd/aidlc/scripts/status-integrity.cjs
4 pre-existing missing Bolt 009 story-reference inconsistencies; none from this bolt
```

### Issues Found During Test

The final audit added an end-to-end picker-to-guided-session test and retained acknowledgement for
malformed legacy rebook callbacks. No unresolved implementation or regression issue remains.

The framework validators were also run. Their repository-wide baseline predates this intent: 34 old
stories use global `US-*` frontmatter IDs that the validator compares to local numeric filenames, and
Bolt 009 contains four stale story references. Those unrelated historical artifacts were not rewritten;
the new intent, unit, stories, and bolt produced no additional finding.

### Remaining Verification

Telegram client rendering and Bot API command-menu caching require one operator smoke test after the
approved bolt closure, git delivery, and VPS rebuild. Expected behavior: typing `/` shows the scoped
command list; sending `/checks`, `/rebook`, or `/admin` without arguments presents the corresponding
buttons. Existing typed forms remain available.

Pre-existing untracked `.agents/` and `AGENTS.md` remain outside this bolt.
