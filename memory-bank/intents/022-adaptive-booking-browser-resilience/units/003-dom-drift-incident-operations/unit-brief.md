---
unit: 003-dom-drift-incident-operations
intent: 022-adaptive-booking-browser-resilience
phase: inception
status: complete
created: 2026-08-13T01:59:59.000Z
updated: 2026-08-13T01:59:59.000Z
default_bolt_type: ddd-construction-bolt
---

# Unit Brief: DOM-Drift Incident Operations

## Purpose

Turn unrecovered browser drift into a deduplicated owner-visible maintenance incident while keeping
all page/account evidence encrypted locally, content-free in Telegram/logs, and automatically
deleted after seven days.

## Scope

### In Scope

- User-independent, content-free DOM failure fingerprints and restart-safe incident correlation.
- Immediate and repeated-assistance thresholds, deterministic resolution evidence, and notification
  suppression.
- Owner-only Telegram alerts with incident ID and local diagnostic command.
- Encrypted local screenshot/structure/result bundles, sanitization, owner access, expiry, and purge.
- Delivery retry, config/status visibility, schema migration, and deterministic operations tests.

### Out of Scope

- Browser recovery and terminal diagnosis generation, owned by Unit 2.
- Model routing, pricing, and dollar admission, owned by Unit 1.
- Sending screenshots/page text through Telegram or uploading evidence to an external backend.
- Autonomous source changes, issue creation, deployment, or provider switching after an incident.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-8 | Detect and correlate likely DOM-drift incidents | Must |
| FR-9 | Notify the owner with actionable, content-free evidence | Must |
| FR-10 | Retain encrypted diagnostics for seven days | Must |

## Domain Concepts

- **DomDriftFingerprint**: User-independent digest of step, safe structure, verifier, and terminal class.
- **DomDriftIncident**: Restart-safe aggregate with state, count, timestamps, severity, and alert state.
- **OwnerIncidentNotice**: Allowlisted content-free Telegram payload.
- **DiagnosticBundle**: Encrypted bounded screenshot, sanitized structure, outcomes, and model metadata.
- **EvidenceRetentionPolicy**: Seven-day expiry plus startup/maintenance/user-purge enforcement.

## Key Operations

| Operation | Description | Inputs | Outputs |
|-----------|-------------|--------|---------|
| Correlate occurrence | Open/update/resolve a safe incident | Diagnosis, structural signature, clock | Incident and alert decision |
| Notify owner | Deliver deduplicated safe message | Incident, owner identity | Delivery audit/retry state |
| Store bundle | Sanitize, encrypt, and retain evidence | Bounded final evidence, incident ID | Owner-scoped bundle metadata |
| Purge evidence | Delete expired or user-purged source evidence | Clock/user scope | Purge audit |

## Story Summary

| Metric | Count |
|--------|-------|
| Total Stories | 3 |
| Must Have | 3 |
| Should Have | 0 |
| Could Have | 0 |

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-137 | Correlate DOM-drift incidents | Must | Planned |
| US-138 | Notify owner of maintenance required | Must | Planned |
| US-139 | Retain encrypted incident diagnostics | Must | Planned |

## Dependencies

### Depends On

- `002-dom-resilient-browser-workflows` terminal diagnosis and safe structural signature.
- Existing SQLite migration framework, deployment secret, Telegram owner authorization/notifier,
  maintenance/startup lifecycle, user purge, CLI, and `/status` diagnostics.

### Depended By

- Production operations and future human-directed maintenance workflows.

### External Dependencies

- **Telegram Bot API**: Owner incident delivery - Risk: Medium.
- **VPS local persistence**: Encrypted seven-day evidence and incident audit - Risk: Medium.

## Technical Context

- Persist only allowlisted incident fields in ordinary SQLite columns and logs.
- Encrypt the full bundle before storage using the existing deployment secret and authenticated
  encryption conventions; keep files/rows owner-controlled and size-bounded.
- Use the existing daemon lifecycle for retry and purge work, not a new scheduler/process.
- Keep incident fingerprints stable across users but non-reversible to page/account content.

## Constraints

- Telegram contains no user, reservation, property, stay, URL/query, page text, screenshot, prompt,
  provider response, cookie, token, or key material.
- One alert per fingerprint per six hours unless severity/class changes.
- Evidence expires after exactly seven days and explicit user purge removes applicable source data.
- Incident handling never delays browser cleanup or starts another browser job.

## Success Criteria

### Functional

- [ ] Maintenance-required diagnoses alert immediately; repeated model-assisted fingerprints alert
  on occurrence two even when the model recovered the browser step.
- [ ] Incident state, deduplication, delivery retry, and resolution survive restart.
- [ ] Owner alerts are actionable and content-free.
- [ ] Bundles are encrypted, owner-readable only, bounded, and inaccessible after seven days.
- [ ] `/status` and CLI expose safe incident/delivery/evidence state.

### Non-Functional

- [ ] Zero sensitive fields in Telegram and ordinary logs across adversarial fixtures.
- [ ] Corrupt/missing key/evidence and Telegram outage produce explicit safe operations outcomes.
- [ ] Incident operations never interfere with coordinator/browser cleanup.

## Bolt Suggestions

- `044-dom-drift-incident-operations`: one DDD bolt for US-137 through US-139 after bolt 043.
