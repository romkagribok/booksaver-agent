---
stage: test
bolt: 018-interactive-command-navigation
created: 2026-07-18T23:02:32Z
---

## Test Report: Telegram Callback Result Reliability

### Summary

- **Focused tests**: 62/62 passed
- **Full tests**: 668/668 passed
- **Ruff**: clean across `src/` and `tests/`
- **Mypy**: clean across 73 source files
- **Diff hygiene**: `git diff --check` passed
- **Dependencies/schema**: unchanged

### Test Files

- [x] `tests/unit/telegram/test_client.py` - Real Boolean Bot API action responses.
- [x] `tests/unit/telegram/test_commands_readonly.py` - Checks acknowledgement/render isolation and
  warning behavior.
- [x] `tests/unit/telegram/test_rebook_gate.py` - Rebook selection dispatch despite callback UI
  failures.
- [x] Full configured pytest suite - All persistence, monitoring, savings, access, Telegram, and
  guided-rebook regressions.

### Acceptance Criteria Validation

- ✅ **Boolean actions**: `answerCallbackQuery` and `deleteMessage` return success from JSON `true`
  without object conversion.
- ✅ **Checks remain visible**: Failed acknowledgement cannot suppress the scoped history edit.
- ✅ **Failures are observable**: Failed checks acknowledgement/edit operations produce warnings and
  remain contained.
- ✅ **Rebook dispatch survives UI failure**: A valid selection reaches the existing ownership check
  and guided session after acknowledgement and picker edit both fail.
- ✅ **Compatibility retained**: Message-returning client methods, callback authorization, typed
  commands, nonce confirmation, and guided-rebook safety remain unchanged.

### Commands and Results

```text
python3 -m ruff check src/ tests/
All checks passed!

python3 -m mypy src/
Success: no issues found in 73 source files

python3 -m pytest tests/unit/telegram/test_client.py \
  tests/unit/telegram/test_commands_readonly.py \
  tests/unit/telegram/test_rebook_gate.py -q
62 passed in 1.98s

python3 -m pytest -q
668 passed in 5.25s

git diff --check
passed
```

### Issues Found

The production defect was reproduced at the client seam: Telegram returns Boolean `true`, while the
old wrapper attempted a mapping conversion after the tap had already been acknowledged. Handler tests
also exposed that checks acknowledgement and rendering shared one exception boundary. Both causes are
covered directly.

### Remaining Verification

After approval, bolt closure, git delivery, and VPS rebuild, tap the booking offered by `/checks`.
The picker message should be replaced by its recent history or the explicit no-checks result.

Pre-existing untracked `.agents/` and `AGENTS.md` remain outside this bolt.
