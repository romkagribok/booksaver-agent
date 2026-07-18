---
stage: plan
bolt: 018-interactive-command-navigation
created: 2026-07-18T22:57:59Z
---

## Implementation Plan: Telegram Callback Result Reliability

### Objective

Fix the deployed `/checks` picker failure at the Telegram client boundary and ensure acknowledgement
failures cannot suppress visible results or valid scoped operation dispatch.

### Deliverables

- Correct Boolean return contracts for Telegram action endpoints.
- Independent acknowledgement and rendering error handling for `/checks`.
- Independent acknowledgement, picker rendering, and guided-operation dispatch for `/rebook`.
- Warning logs for failed callback acknowledgement/edit operations.
- Transport and handler regressions reproducing real Telegram responses and partial failures.

### Dependencies

- Existing `TelegramBotClient`, callback router, user-scoped check-history operation, and guided
  rebook ownership checks.
- No new runtime dependency, schema, service, or process.

### Technical Approach

Return `bool(result)` from Boolean Bot API methods while keeping map-returning methods unchanged.
Split callback side effects into separate guarded calls so one Telegram write cannot suppress the
next operation. Exercise the actual JSON `true` transport response and injected failure combinations.

### Acceptance Criteria

- [x] `answerCallbackQuery` and `deleteMessage` accept real JSON Boolean success results.
- [x] `/checks` attempts its edit after either acknowledgement success or failure.
- [x] `/rebook` invokes the ownership-checked selection after acknowledgement/edit failures.
- [x] Failures have useful warnings and do not escape the handler.
- [x] Existing callback authorization and typed behavior remain unchanged.
- [x] Focused/full tests plus Ruff, mypy, and diff checks pass.

### Process Authorization

The product owner diagnosed the deployed behavior with the agent and explicitly authorized applying
the proposed production hotfix on 2026-07-18.
