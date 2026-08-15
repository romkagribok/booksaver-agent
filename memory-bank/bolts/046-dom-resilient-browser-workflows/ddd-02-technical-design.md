---
stage: design
bolt: 046-dom-resilient-browser-workflows
created: 2026-08-14T03:11:51.000Z
---

# Technical Design: Atomic Remote-Authentication Finalization

## Architecture Pattern

Retain the existing hexagonal single-process architecture. The application-layer
`RemoteAuthenticationManager` remains the aggregate boundary for lifecycle/capture ordering;
Playwright remains an infrastructure producer of a terminal browser result; the encrypted session
repository and incident recorder remain injected driven adapters; the Mini App remains a polling
presentation adapter.

No database migration, new service, dependency, browser process, coordinator, model prompt, or model
authority is introduced.

## Layer Responsibilities

### Domain

- Add `RemoteAuthStatus.FINALIZING` as non-terminal.
- Preserve the terminal set: `SUCCEEDED`, `FAILED`, `EXPIRED`, and `CANCELLED`.
- Preserve existing failure values and use `CAPTURE_REJECTED` for persistence/import failure.

### Application

- Extend `RemoteBrowserRunner.run` with `on_finalizing: Callable[[], bool]`.
- Add an optional sanitized `IncidentDraft` to `RemoteBrowserResult`; cookies and incident evidence
  remain separate fields with constructor invariants.
- `RemoteAuthenticationManager._begin_finalizing` atomically changes only `READY` or `CONNECTED` to
  `FINALIZING`; it returns false if cancellation, expiry, purge, or shutdown already won.
- Viewer `cancel()` ignores `FINALIZING`, while `cancel_for_telegram_user()` and `stop_all()` retain
  authority over it.
- The manager persists verified cookies while holding its existing lifecycle lock. Only a successful
  commit may transition `FINALIZING -> SUCCEEDED`.
- The manager records a pending recovered incident only after capture succeeds. If capture rejects,
  it discards that draft, transitions to `FAILED/CAPTURE_REJECTED`, and logs only a safe stage code
  plus exception class.
- Terminal failure incident drafts continue to record after browser cleanup; incident failures never
  change the attempt outcome.

### Infrastructure: Browser Runner

- After deterministic or semantic code verification, serialize the current context cookies and call
  `on_finalizing` before returning success.
- If finalization admission returns false, return `CANCELLED` and discard pending recovered evidence.
- Close page/context/browser/display resources exactly as today before `run()` returns.
- Stop persisting incidents inside `SystemRemoteBrowserRunner`; attach the already-sanitized draft to
  the result for application-layer post-capture ordering.
- Opus remains diagnosis-only and cannot reach this success boundary.

### Infrastructure: Runtime Composition

- Inject the existing `DomIncidentRecorder` sink into `RemoteAuthenticationManager`, not the runner.
- Keep the sink context-managed and short-lived. The manager invokes it only after runner cleanup.
- Keep `UserSessionService.import_cookies` and `EncryptedUserSessionRepository` unchanged.

### Presentation: Telegram Mini App

- Poll `finalizing` as a distinct non-terminal state, replace any stale RFB error with
  “Authentication verified; saving…”, disable all browser and cancel controls, disconnect RFB, and
  continue short polling.
- Suppress `pagehide` cancellation once `finalizing` has been observed. Server-side cancel refusal
  remains authoritative if pagehide races before that poll.
- On `succeeded`, disconnect controls and call `Telegram.WebApp.close()` when present.
- On `failed`, `expired`, or `cancelled`, leave the status visible. Capture rejection gets specific
  safe retry guidance; no exception message reaches the viewer or Telegram.

## Contracts

### Runner Contract

```python
run(
    work: RemoteBrowserWork,
    daemon_stop_event: threading.Event,
    on_ready: Callable[[], None],
    on_finalizing: Callable[[], bool],
) -> RemoteBrowserResult
```

- `on_finalizing()` is called at most once and only after code verification.
- `False` means a higher-priority lifecycle outcome already won; no success or recovered incident is
  returned.
- A successful result contains cookie JSON and may contain one sanitized pending incident draft.

### Cancellation Precedence

1. Administrative purge/revocation and daemon shutdown always retain authority.
2. Explicit viewer cancel/pagehide wins in `STARTING`, `READY`, or `CONNECTED`.
3. Code verification admitted by `_begin_finalizing` closes ordinary viewer cancellation authority.
4. Existing permanent revocation marker remains the final storage-level race defense.

### Commit Ordering

```text
code verification receipt
  -> manager finalizing latch
  -> browser and display cleanup
  -> encrypted session capture
  -> recovered incident publication (best effort)
  -> terminal succeeded state
  -> post-connect synchronization and Telegram success notification
  -> Mini App observes succeeded and closes
```

If any step through encrypted capture fails, later success steps do not run. Incident persistence is
best effort after capture and cannot undo a committed session.

## Failure Mapping and Observability

- `finalization_started`: info, no identifiers.
- `finalization_succeeded`: info, no identifiers.
- `finalization_cancelled_before_commit`: info, no identifiers.
- `finalization_capture_rejected`: warning plus exception class only.
- `finalization_incident_record_failed`: warning, no exception text or evidence.

Cookies, launch/viewer/WebSocket capabilities, Telegram/local user IDs, URLs, page text, labels,
reservation fields, incident diagnostics, and exception messages remain prohibited in ordinary logs.

## Data and Migration Design

No persisted schema changes. `FINALIZING` is in-memory only. Existing encrypted session bundle
format, SQLite schema 15, incident tables, and diagnostics envelope remain unchanged.

## Security and Privacy

- Model classifications still cannot save cookies; an existing code verification receipt is required.
- Finalization does not keep browser authority alive during persistence.
- Viewer-close convenience cannot override a verified commit, but administrative purge and permanent
  revocation retain their stronger privacy authority.
- Incident content remains sanitized before browser cleanup and encrypted only after cleanup.
- Safe failure messages do not reveal storage paths, cookie counts/domains, user identity, or provider
  content.

## Test Design

### Application Unit Tests

- Observe `FINALIZING` while a controllable runner is between verification and return.
- Ordinary viewer cancellation during finalizing is refused; session capture and success complete.
- Pre-verification cancel still wins.
- Administrative cancel during finalizing wins and capture does not run.
- Capture rejection produces typed failure, safe log class, no notification, and no incident record.
- Recovered incident is recorded after capture; incident failure does not undo success.

### Browser Runner Unit Tests

- Deterministic and Sonnet-assisted success invoke finalization admission exactly once.
- Rejected finalization returns cancellation with no cookies or incident draft.
- Opus/model-only outcomes never invoke finalization.
- Runner returns sanitized evidence only after cleanup and performs no persistence itself.

### Viewer and Gateway Tests

- `finalizing` disables controls, suppresses pagehide cancel, disconnects RFB, and continues polling.
- `succeeded` calls Telegram close; failed capture remains visible and does not auto-close.
- Missing Telegram close capability leaves committed-success guidance visible.

### Integration and Regression

- Purge/capture race and replacement-attempt tests remain green.
- Production-shaped changed `/mytrips` recovery reaches finalizing, persists once, records one
  recovered occurrence, and closes without page reload or cancellation.
- Full Ruff, strict mypy, pytest, CLI smoke, AI-DLC artifact/status validators, and diff hygiene pass.

## ADR Analysis Input

The design applies ADR-024, ADR-026, ADR-032, ADR-033, and ADR-034 plus the reviewed Bolt 028/031
cancellation patterns. It introduces no new architectural pattern, persistence strategy, dependency,
security boundary, or external contract that warrants a new ADR.
