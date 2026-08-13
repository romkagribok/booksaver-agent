---
id: 003-retain-encrypted-incident-diagnostics
unit: 003-dom-drift-incident-operations
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 044-dom-drift-incident-operations
implemented: true
---

# Story: Retain Encrypted Incident Diagnostics

## User Story

**As a** BookSaver owner maintaining the self-hosted deployment
**I want** a short-lived encrypted DOM-drift evidence bundle
**So that** I can reproduce code breakage without exposing account data through Telegram or logs

## Acceptance Criteria

- [ ] **Given** a DOM-drift incident opens, **When** final evidence is available, **Then** exactly one
  bounded bundle stores the screenshot, sanitized visible structure, structured outcomes, typed
  diagnoses, ordered model attempts, and safe budget metadata encrypted with the deployment secret.
- [ ] **Given** raw evidence contains credentials, input values, cookies, scripts, query strings,
  confirmation/user identifiers, or free-form reasoning, **When** sanitization runs, **Then** those
  fields are removed before encryption and never appear in ordinary storage/logs.
- [ ] **Given** a trusted owner invokes the diagnostic command with an incident ID, **When** evidence
  is valid and unexpired, **Then** it decrypts locally under owner authorization without Telegram
  transmission; other callers receive no existence disclosure.
- [ ] **Given** seven days pass, the daemon starts, maintenance runs, or an applicable user is purged,
  **When** retention is enforced, **Then** expired/source evidence is deleted and cannot be recovered
  through BookSaver.
- [ ] **Given** encryption key/evidence is missing, corrupt, expired, oversized, or undecryptable,
  **When** inspected, **Then** the owner receives an explicit safe status and the incident/alert
  remains available without evidence.
- [ ] **Given** process/file permissions are inspected, **When** a bundle is stored, **Then** it uses
  existing owner-controlled path and restrictive persistence conventions.

## Technical Notes

- Reuse the existing deployment-secret authenticated-encryption facility where possible.
- Prefer an encrypted envelope plus content-free SQLite metadata; never plaintext PNG snapshots for
  this incident path.
- Inject clocks and storage/encryption failures in tests.

## Dependencies

### Requires

- US-137, existing secret configuration, persistence migrations, maintenance cadence, and user purge.

### Enables

- Reviewable local code-maintenance evidence and seven-day privacy enforcement.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Screenshot exceeds bundle limit | Store bounded/downscaled evidence or explicit omitted status |
| Sanitization fails | Do not store raw evidence; retain content-free incident |
| Secret rotates | Old evidence reports undecryptable and expires normally; no plaintext fallback |
| Incident aggregates multiple users | Bundle/source linkage remains encrypted and purge-safe |

## Out of Scope

- Cloud upload, Telegram attachment, long-term archive, or automatic code generation from evidence.
