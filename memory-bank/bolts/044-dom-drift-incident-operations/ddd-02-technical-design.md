---
unit: 003-dom-drift-incident-operations
bolt: 044-dom-drift-incident-operations
stage: design
status: complete
updated: 2026-08-13T03:10:00Z
---

# Technical Design - DOM Drift Incident Operations

## Architecture

Unit 2 emits an in-memory sanitized `IncidentDraft` beside its typed terminal/recovery result. The
coordinator captures it while the page exists, then closes Playwright and releases the browser gate
before calling the incident sink. A separate supervised lifecycle worker performs encryption,
persistence maintenance, notification delivery, retries, and retention.

```text
browser result + in-memory draft
        |
        v
close browser / release coordinator gate
        |
        v
correlate transaction --> content-free incident + alert generation
        |                                  |
        v                                  v
sanitize/encrypt bundle             lifecycle delivery worker
        |                                  |
        v                                  v
encrypted SQLite BLOB               owner Telegram only
```

## Layer Changes

- `domain/dom_incident.py`: closed fingerprint, occurrence, incident, notice, bundle, status, and
  safe projection types.
- `application/dom_incident.py`: eligibility filter, correlation policy, bundle sanitizer/encrypter
  orchestration, notice construction, retention/retry worker, and status projection.
- `infrastructure/persistence/dom_incident.py`: transactional SQLite repository.
- `infrastructure/persistence/encrypted_diagnostics.py`: Fernet envelope adapter using
  `FernetKeyStore(purpose="DOM-drift diagnostic")`.
- `infrastructure/notifications/owner_incident.py`: typed renderer/sender targeting only configured
  `owner_chat_id` through the shared `TelegramBotClient`.
- Composition root injects one incident sink into the coordinator and one
  `dom-drift-incidents` supervised service runner into daemon lifecycle.

## Schema v15

### `dom_drift_incidents`

Fingerprint-unique incident ID, allowlisted journey/step/terminal/verifier/model-role codes, state,
severity, recovered flag, total and six-hour-window occurrence counts, first/last occurrence,
opened/resolved times, alert suppression time, and evidence state. No caller/content columns.

### `dom_drift_alerts`

Alert ID/generation, incident ID, severity, durable delivery state, attempt count, next attempt,
claimed/delivered timestamps, and allowlisted delivery failure code. A unique incident/generation
key prevents duplicate sends.

### `dom_drift_diagnostics`

One row per incident with envelope version, bounded ciphertext BLOB, byte size, created/expires
times, and safe evidence state. No plaintext data or source identity columns.

`BEGIN IMMEDIATE` correlation ensures simultaneous callers cannot create duplicate incidents or
alerts. Additive v14→v15 migration preserves spend/qualification and all existing data.

## Correlation and Resolution

- Reject all predictable/non-DOM terminal codes before fingerprint construction.
- Canonical fingerprint JSON includes only journey, stable step, terminal class, verifier category,
  structural digest, and ordered model roles.
- `code_maintenance_required` opens immediately.
- Other eligible assisted success/failure records remain observing until the second identical
  occurrence inside six hours, then open/update one incident and request one alert.
- A deterministic success event for journey/step resolves matching observing/open incidents and
  suppresses any pending stale generation. Assisted success increments evidence but does not
  resolve.

## Evidence Sanitization and Encryption

Accept only fixed typed outcomes and safe structural events such as
`TraceRecorder.export_operational_events()`. Never reuse `SnapshotWriter`, because it writes page
text and PNG data in plaintext and lacks seven-day/purge semantics.

For the optional image, temporarily inject styling into the live page that hides all text, form
values/placeholders, images, SVG, canvas, video, and background images before capture. Restore the
page afterward. If transformation, capture, size validation, or restoration cannot be proven safe,
omit the image and mark evidence unavailable; never encrypt an unsanitized fallback.

Serialize a versioned bounded envelope, encrypt it with the deployment secret, and persist only
ciphertext. Missing/wrong/rotated key, corruption, or oversize remains an explicit evidence state.
Retention purges at startup and periodically; `expires_at = created_at + 7 days` exactly.

Applicable user purge decrypts source linkage and deletes matching evidence before the user row is
removed. If active ciphertext cannot be decrypted, conservatively delete unverifiable diagnostic
ciphertext while retaining content-free incident metadata.

## Owner Notification

The renderer accepts `OwnerIncidentNotice` only and emits incident ID, registered journey/step,
safe category, recovered state, occurrence count, ordered model roles, provider/budget state,
evidence status, and `booksaver incidents inspect INCIDENT_ID`.

It bypasses ordinary caller routing and the silently dropping per-chat reply limiter. It never uses
`NotificationDispatcher`, `OwnerBookingNotifierResolver`, or `resolve_telegram_chat_id`. Delivery
failure logs contain only incident ID and typed state, never Telegram response/exception text.

The worker marks in-flight before send. Known failures use bounded one/five/thirty-minute backoff.
A stale in-flight record after restart becomes `delivery_unknown` and remains suppressed for the
six-hour window to avoid a possible duplicate after an ambiguous crash.

## Operator Interfaces

- `/status`: owner-only counts for open incidents, pending/failed alerts, and unavailable evidence;
  invited users receive no global incident state.
- `booksaver incidents list`: content-free incident projections.
- `booksaver incidents inspect UUID`: strict UUID parsing and local-only decryption. No Telegram
  inspection command accepts or returns decrypted evidence.

## Verification

- Threshold, concurrency, restart/deduplication, deterministic resolution, and assisted
  non-resolution tests.
- Known auth/provider/budget/etc inputs prove zero incident and zero diagnosis call.
- Adversarial source fields prove no PII/URL/query/prompt/response/cookie/key in metadata,
  Telegram, or logs.
- Encryption, wrong-key/corruption/oversize, exact seven-day expiry, startup maintenance, and user
  purge tests.
- Owner-only delivery/status, retries, stale in-flight, missing config, and suppression tests.
- Lifecycle ordering test proves browser closes before incident persistence and incident/Telegram
  failure cannot alter caller completion.
