---
unit: 003-dom-drift-incident-operations
bolt: 044-dom-drift-incident-operations
stage: model
status: complete
updated: 2026-08-13T03:10:00Z
---

# Static Model - DOM Drift Incident Operations

## Bounded Context

This context turns maintenance-worthy, model-assisted DOM outcomes into durable content-free
incidents, owner-only alerts, and short-lived encrypted local evidence. It does not classify pages,
operate a browser, make booking decisions, expose diagnostics to callers, change source code, open
GitHub issues, or deploy fixes.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `DomDriftOccurrence` | fingerprint, registered journey/step, terminal class, verifier category, structural digest, ordered model roles, provenance, recovered flag, observed time | Contains no caller, booking, property, stay, URL, page text, screenshot, prompt/response, or exception text |
| `DomDriftIncident` | incident ID, fingerprint, state, severity, occurrence/window counts, timestamps, alert/evidence status | One durable aggregate per fingerprint; deterministic success resolves; assisted success does not |
| `OwnerIncidentNotice` | allowlisted incident metadata and local inspection command | Owner chat only; final rendered payload accepts no arbitrary source text |
| `DiagnosticBundle` | version, sanitized structure, typed outcomes/diagnosis, ordered attempts, safe budget metadata, optional text-free image, encrypted source linkage | Bounded, encrypted before persistence, expires after seven days; no plaintext fallback |
| `IncidentAlert` | generation, delivery state, attempts, retry time, safe failure code | At most one generation per fingerprint/six hours unless severity changes |

## Value Objects

- `DomDriftFingerprint`: SHA-256 of canonical allowlisted machine fields only.
- `StructuralDigest`: non-reversible digest of sanitized structural roles/categories, never source
  text or selector values.
- `IncidentSeverity`: observing, maintenance-required.
- `IncidentState`: observing, open, resolved.
- `DeliveryState`: pending, in-flight, delivered, retryable-failed, failed, delivery-unknown,
  suppressed.
- `EvidenceState`: pending, available, unavailable, expired, purged, corrupt, undecryptable,
  oversized.
- `IncidentSourceProvenance`: Sonnet-assisted, Opus-assisted, model-diagnosed,
  code-maintenance-required.

## Aggregates and Invariants

1. Predictable auth/MFA/captcha/bot-wall, provider/key/rate-limit, budget/time, observation, safety,
   deterministic business, and infrastructure outcomes create no DOM incident and no
   explanation-only model call.
2. A `code_maintenance_required` diagnosis opens immediately. Other eligible identical assisted
   fingerprints open on the second occurrence within six hours.
3. Correlation is deployment-wide but user-independent; no caller identity enters fingerprint or
   content-free metadata.
4. Deterministic success for the registered step resolves observing/open incidents and suppresses
   pending stale alerts. Assisted success never resolves them.
5. Notification generation is transactionally deduplicated for six hours unless severity changes.
6. Exactly one encrypted bundle may exist per incident; source-user linkage exists only inside the
   ciphertext for conservative purge.
7. Expired, purged, corrupt, oversized, or undecryptable evidence does not remove the incident or
   prevent its content-free owner alert.
8. Browser cleanup and caller response complete before incident persistence or Telegram delivery.

## Story Coverage

- **US-137**: content-free fingerprint, transactional correlation, thresholds, resolution, and
  restart-safe deduplication.
- **US-138**: typed owner notice, durable delivery state, retry/suppression, and owner-only status.
- **US-139**: sanitized bounded bundle, deployment-secret encryption, local inspection, seven-day
  retention, and purge behavior.
