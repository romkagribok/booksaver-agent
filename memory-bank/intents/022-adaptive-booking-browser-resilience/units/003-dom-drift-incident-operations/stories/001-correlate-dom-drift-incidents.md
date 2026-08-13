---
id: 001-correlate-dom-drift-incidents
unit: 003-dom-drift-incident-operations
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 044-dom-drift-incident-operations
implemented: true
---

# Story: Correlate DOM-Drift Incidents

## User Story

**As a** BookSaver owner
**I want** repeated model-assisted browser seams grouped into maintenance incidents
**So that** the LLM can keep service running while I still learn which deterministic code drifted

## Acceptance Criteria

- [ ] **Given** a model-assisted recovery or diagnosis, **When** the occurrence is recorded, **Then**
  its fingerprint uses only journey, named step, terminal class, verifier category, sanitized
  structural signature, and model roles—not user, reservation, URL, text, or screenshot content.
- [ ] **Given** the final diagnosis is `code_maintenance_required`, **When** it is recorded, **Then**
  an incident opens immediately and requests owner notification.
- [ ] **Given** the same fingerprint occurs twice within six hours, **When** both occurrences are
  model-assisted successes or failures, **Then** one incident opens/updates and requests one alert.
- [ ] **Given** the same step later succeeds deterministically without model assistance, **When**
  resolution is recorded, **Then** the incident becomes resolved and stale alerts are suppressed;
  LLM-assisted success alone does not resolve it.
- [ ] **Given** the daemon restarts or different invited users encounter the seam, **When** correlation
  continues, **Then** counts/deduplication persist without exposing or combining caller data.

## Technical Notes

- Model quality incidents (`Sonnet weak, Opus recovered`) remain distinguishable from code DOM drift.
- Store non-reversible bounded structural digests, not fingerprint source material.
- Use transactional occurrence/update logic.

## Dependencies

### Requires

- US-136 terminal diagnosis and sanitized structural signature.

### Enables

- US-138 and US-139.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Same step but different terminal class | Separate or severity-upgraded incident per policy |
| Occurrences straddle six-hour boundary | No repeated threshold until two fall inside a window |
| User is purged after occurrence | Incident remains content-free; source evidence is removed |

## Out of Scope

- Automatic source changes, GitHub issues, deployments, or model-profile replacement.
