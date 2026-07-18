---
unit: 001-on-demand-check-orchestration
intent: 007-telegram-on-demand-checks
phase: construction
status: complete
unit_type: application-service
default_bolt_type: simple-construction-bolt
created: 2026-07-18T23:40:00Z
updated: 2026-07-18T23:57:35Z
---

# Unit Brief: On-Demand Check Orchestration

## Purpose and Scope

Provide a discoverable, scoped, responsive Telegram immediate-check command and make one shared
application service authoritative for all scheduled/manual browser work, limits, persistence,
savings evaluation, and notifications.

## Assigned Requirements

- FR-1 through FR-5 from Intent 007.

## Key Entities and Operations

- **Check coordinator**: Daemon-lifetime browser admission, counters, monitor pipeline, and workers.
- **Check request**: Requesting Telegram identity/chat plus an untrusted booking selector.
- **Daily budget**: Thread-safe UTC-day check and actual LLM-call counts per local user.
- **Immediate result**: Accepted/busy/refused admission followed by a persisted monitor result.

## Technical Constraints

- One global browser gate; no queue, competing browser, second scheduler, or duplicate pipeline.
- Worker-time ownership/status re-resolution and shutdown checks.
- Per-check LLM allowance capped to remaining daily calls; zero means DOM/scripted-only.
- Preserve monitor never-raise behavior, trace persistence, check history, failure tracking, savings,
  key-invalid notices, and owner routing.
- No schema or dependency change.

## Stories

- US-052: Discover and select an immediate check.
- US-053: Run a responsive authorized background check.
- US-054: Serialize scheduled and immediate check work.
- US-055: Share and enforce daily check/LLM budgets.
- US-056: Reuse the complete monitoring outcome pipeline.

## Success Criteria

- [x] Picker, typed selector, callback, and completion are caller scoped.
- [x] Telegram polling remains responsive during browser work.
- [x] Scheduled/manual work cannot overlap or duplicate a booking execution.
- [x] Both paths consume the same correct daily counters.
- [x] Immediate results persist, trace, detect savings, and notify normally.
- [x] All scoped quality and AI-DLC validation gates pass (legacy findings remain).
