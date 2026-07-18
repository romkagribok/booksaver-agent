---
stage: implement
bolt: 018-interactive-command-navigation
created: 2026-07-18T23:02:32Z
---

## Implementation Walkthrough: Telegram Callback Result Reliability

### Summary

Telegram Boolean action responses now retain their real success contract, and booking/savings picker
callbacks isolate acknowledgement, message rendering, and protected operation dispatch. The deployed
`/checks` tap can therefore render history after Telegram acknowledges it instead of stopping on an
invalid Boolean-to-map conversion.

### Structure Overview

The correction stays inside the existing Telegram outbound and inbound adapters. The client owns Bot
API response shapes; feature callbacks independently contain and log non-critical Telegram write
failures while their existing scoped persistence operations remain authoritative.

### Completed Work

- [x] `src/booksaver/infrastructure/telegram/client.py` - Returns Boolean success for Telegram action
  methods without changing message-object methods.
- [x] `src/booksaver/infrastructure/telegram/commands_readonly.py` - Separates checks acknowledgement
  from result rendering and records either failure.
- [x] `src/booksaver/infrastructure/telegram/rebook_gate.py` - Separates picker acknowledgement and
  edit failures from ownership-checked guided-session dispatch.
- [x] `tests/unit/telegram/test_client.py` - Reproduces Telegram's real JSON Boolean action results.
- [x] `tests/unit/telegram/test_commands_readonly.py` - Verifies result rendering after failed
  acknowledgement and observable containment of edit failures.
- [x] `tests/unit/telegram/test_rebook_gate.py` - Verifies valid selection dispatch after both callback
  UI writes fail.

### Key Decisions

- **Endpoint-specific response types**: Boolean action endpoints return `bool`; message endpoints
  remain mappings.
- **Independent callback effects**: Acknowledgement, rendering, and operation dispatch do not share a
  failure boundary.
- **No retry loop**: Failures are visible in logs but not retried, avoiding duplicate or late protected
  operations.

### Deviations from Plan

None.

### Dependencies Added

None.

### Developer Notes

The original unit fake returned a mapping for `answerCallbackQuery`, which differs from Telegram's
production Boolean response. Transport-level tests now pin the actual contract.
