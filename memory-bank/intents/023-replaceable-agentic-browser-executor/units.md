---
intent: 023-replaceable-agentic-browser-executor
phase: inception
status: complete
created: 2026-08-16T19:18:41Z
updated: 2026-09-03T23:32:00Z
---

# Units: Replaceable Agentic Browser Executor

## Unit Decomposition

### 001-agentic-executor-control-plane

- **Purpose**: Define provider-neutral contracts, owner-bound session leases, BookSaver validation,
  cost accounting, fake execution, and routing without changing production routing.
- **Assigned Requirements**: FR-1, FR-2, FR-3, FR-6, FR-7
- **Dependencies**: Existing coordinator, session vault, model budget, offer policy, and legacy monitor.

### 002-local-agentic-price-executor

- **Purpose**: Implement the local Stagehand semantic path and guarded Anthropic computer-use fallback
  for complete price-check navigation and rate perception.
- **Assigned Requirements**: FR-4, FR-5, FR-8
- **Dependencies**: Unit 001 and the existing transient Chromium/browser lease.

### 003-agentic-browser-qualification

- **Purpose**: Prove safety, DOM resilience, privacy, cost, and reliability; govern owner canary,
  invited-user promotion, and regression rollback.
- **Assigned Requirements**: FR-9
- **Dependencies**: Units 001 and 002.

### 004-agentic-inventory-executor

- **Purpose**: Replace selector-dependent inventory perception with provider-neutral agentic
  executors while preserving positive-only reconciliation; `/bookings` first qualified local
  Browser Use and Unit 006 expands it to every agentic inventory trigger.
- **Assigned Requirements**: FR-10, FR-12
- **Dependencies**: Units 001 and 002; existing account synchronization and reconciliation policy.

### 005-legacy-price-selector-retirement

- **Purpose**: Retire the legacy price path only after price promotion and the complete rollback
  window.
- **Assigned Requirements**: FR-11
- **Dependencies**: Unit 003 promotion approval, Unit 006 Browser Use qualification, and 30 days
  without rollback.

### 006-browser-use-price-executor

- **Purpose**: Make local Browser Use the default provider-neutral price executor for manual and
  scheduled checks, remove the Stagehand inventory prerequisite, preserve explicit
  Stagehand/deterministic rollback, version qualification, and prove the deployed path with an
  operator-only replay.
- **Assigned Requirements**: FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20
- **Dependencies**: Units 001, 002, 003, and 004; existing coordinator, price validation,
  qualification ledger, and Browser Use runtime.

### 007-shared-browser-use-access

- **Purpose**: Admit every currently disclosed active invitee to the proven Browser Use inventory
  and price path through an explicit owner-authorized route, and expose secret-safe API funding
  provenance in the owner-only Telegram admin projection.
- **Assigned Requirements**: FR-21, FR-22
- **Dependencies**: Units 001, 003, 004, and 006; Intent 010 aggregate-admin privacy boundary.

## Requirement-to-Unit Mapping

| Requirement | Unit |
|-------------|------|
| FR-1, FR-2, FR-3, FR-6, FR-7 | `001-agentic-executor-control-plane` |
| FR-4, FR-5, FR-8 | `002-local-agentic-price-executor` |
| FR-9 | `003-agentic-browser-qualification` |
| FR-10, FR-12 | `004-agentic-inventory-executor` |
| FR-11 | `005-legacy-price-selector-retirement` |
| FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20 | `006-browser-use-price-executor` |
| FR-21, FR-22 | `007-shared-browser-use-access` |

Each functional requirement is assigned exactly once. Cross-unit constraints remain traced through
dependencies and story acceptance criteria.

## Dependency Graph

```mermaid
flowchart LR
    u1["001 Control plane"] --> u2["002 Local price executor"]
    u1 --> u3["003 Qualification"]
    u2 --> u3
    u1 --> u4["004 Agentic inventory executor"]
    u2 --> u4
    u4 -->|"/bookings adapter"| u4b["Browser Use OSS"]
    u1 --> u6["006 Browser Use price executor"]
    u3 --> u6
    u4 --> u6
    u6 -->|"default price adapter"| u4b
    u6 --> u7["007 Shared Browser Use access"]
    u3 --> u7
    u4 --> u7
    u3 -->|"promotion plus rollback window"| u5["005 Legacy selector retirement"]
    u6 --> u5
```

## Construction Sequence

1. Bolt 050: contracts and control plane; no production routing change.
2. Bolt 051: Stagehand/computer-use adapter and routing modes; `legacy` remains default.
3. Bolt 054: correct Stagehand launch for the non-root Docker runtime and prove exact-image startup.
4. Bolt 052: fixtures, privacy/egress tests, canary ledger, and promotion evaluator. Software can be
   completed, but live qualification remains a real 14-day owner checkpoint.
5. Bolt 053: agentic inventory contracts, adapter, routing, positive-only reconciliation, and
   single-refresh `/checknow`; construction is authorized before price promotion.
6. Bolt 056: layered read-only destination policy and privacy-safe rejection diagnostics.
7. Bolt 057: thread-owned persistent cost accounting across the async Stagehand boundary.
8. Bolt 058: provider-compatible Stagehand extraction and Anthropic computer-use schemas.
9. Bolt 059: version-matched mobile session identity and typed navigation-failure classification.
10. Bolt 060: trigger-specific local Browser Use executor for `/bookings`; every other trigger keeps
   its current executor.
11. Bolt 061: use the canonical HTTPS inventory entry after production showed Booking.com's legacy
    entry redirecting through blocked HTTP before Browser Use could perceive the page.
12. Bolt 062: remove cached-row completion and prove unknown live inventory discovery.
13. Bolt 063: distinguish accepted positive observations from authoritative completeness in the
    `/bookings` outcome and verify the waiting coordinator process exits successfully.
14. Bolt 064: make Browser Use the default price executor for `/checknow` and scheduled work,
    expand it to every agentic inventory prerequisite, add model-view preflight and
    production-equivalent replay, and preserve explicit rollback.
15. Bolt 065: add explicit `consented_users` routing for disclosed invitees and safe owner-only API
    funding/key-presence visibility.
16. Bolt 055: legacy price-selector retirement, blocked until Browser Use price promotion and the
    30-day rollback window pass.
