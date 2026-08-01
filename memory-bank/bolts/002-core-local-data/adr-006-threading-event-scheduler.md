---
unit: 001-core-local-data
bolt: 002-core-local-data
id: ADR-006
title: threading.Event sleep loop as the scheduler mechanism
status: superseded
superseded_by: ADR-029
updated: 2026-07-01T00:00:00Z
---

# ADR-006: threading.Event sleep loop as the scheduler mechanism

> **Superseded by ADR-029** for fixed-interval timing. The interruptible
> `threading.Event.wait(timeout)` mechanism remains in use with adaptive durable daily slots.

## Context

The Scheduler must fire all registered jobs once per `CheckInterval` and stop cleanly
when signalled. Candidates considered:

1. `time.sleep()` loop
2. `threading.Event.wait(timeout)` loop
3. `sched.scheduler` (stdlib)
4. APScheduler (third-party)

## Decision

Use a **`threading.Event.wait(timeout)` loop** — stdlib only, no third-party library.

```python
_stop = threading.Event()

while not _stop.is_set():
    for job in self._jobs:
        try:
            job.handler()
        except Exception as exc:
            log_job_failure(job.name, exc)
    _stop.wait(timeout=interval_seconds)
```

## Rationale

**vs `time.sleep()` loop:** `Event.wait(timeout)` wakes immediately when `_stop` is
set, so a SIGTERM during a long sleep interval shuts the daemon down without waiting
out the full interval. `time.sleep()` cannot be interrupted this way.

**vs `sched.scheduler`:** `sched` is designed for one-shot delayed calls and requires
re-scheduling each job after every run. It adds no benefit over a plain loop for a
fixed-interval repeating pattern and its API is more complex for this use case.

**vs APScheduler:** APScheduler provides cron expressions, jitter, job persistence, and
missed-execution handling — none of which are needed for a single fixed-interval loop
against one job. Adding a third-party runtime dependency conflicts with ADR-003
(stdlib-first, zero runtime deps for the core).

## Consequences

- The scheduler loop runs on the main thread; signal handlers set `_stop` from any
  context, which is safe for `threading.Event`.
- No sub-second precision or cron scheduling in MVP; `CheckInterval` is a whole-minute
  or whole-hour value per the domain model.
- If future requirements add cron scheduling, per-job intervals, or missed-run tracking,
  APScheduler can replace this loop without changing the `Scheduler.register()` contract
  that Unit 2 depends on.
