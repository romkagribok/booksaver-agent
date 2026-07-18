---
id: 003-package-persistence-schema
unit: 001-production-reliability
intent: 004-production-hardening
status: complete
priority: must
created: 2026-07-18T17:48:48Z
assigned_bolt: 013-production-reliability
implemented: true
---

# Story: Package Persistence Schema

**Global story ID**: US-039

## User Story

**As a** BookSaver VPS operator
**I want** the installed Python distribution to contain its SQLite schema
**So that** a fresh container can initialize its persistent data volume without depending on a source checkout

## Acceptance Criteria

- [ ] **Given** a wheel is built from the repository, **When** its archive contents are inspected,
  **Then** `booksaver/infrastructure/persistence/schema.sql` is present.
- [ ] **Given** BookSaver is installed from that wheel with an empty data directory, **When**
  persistence initializes, **Then** it does not raise a missing-schema `FileNotFoundError`.
- [ ] **Given** the packaging declaration is added, **When** schema and migration tests run, **Then**
  their existing behavior remains unchanged.

## Technical Notes

- Declare the SQL resource as setuptools package data in `pyproject.toml`.
- Add a regression test that inspects packaging configuration without requiring Docker.
- Verify the actual built wheel archive as construction evidence.

## Dependencies

### Requires

- Intent 001 SQLite persistence and intent 003 VPS distribution artifacts.

### Enables

- Fresh Docker/VPS deployment from the reviewed BookSaver wheel.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Editable source installation | Continues to find the same schema file |
| Wheel built in an isolated environment | Resource is still included through package metadata |
| Existing `/data` volume | Opens/migrates normally; packaging change does not rewrite data |

## Out of Scope

- Modifying `schema.sql` or advancing the schema version.
- Changing persistence resource-loading semantics.
- Building or publishing a package to a public registry.
