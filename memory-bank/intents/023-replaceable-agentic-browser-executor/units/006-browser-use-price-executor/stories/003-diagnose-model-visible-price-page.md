---
id: 003-diagnose-model-visible-price-page
unit: 006-browser-use-price-executor
intent: 023-replaceable-agentic-browser-executor
status: draft
priority: must
created: 2026-09-02T23:44:45Z
assigned_bolt: 064-browser-use-price-executor
implemented: false
---

# Story: Diagnose the Model-Visible Price Page Before Paid Inference

## User Story

**As a** BookSaver operator
**I want** unusable Browser Use page state identified before model work
**So that** blank screenshots, broken attachment, authentication redirects, and transport failures
are diagnosable without wasting API budget or retaining private content

## Acceptance Criteria

- [ ] Preflight verifies the active mobile context, settled allowed destination, browser attachment,
  and usable visual or semantic representation before the first paid model call.
- [ ] Detectable blank, signed-out, challenged, internal-error, or unusable empty states return a
  closed terminal outcome with zero paid calls.
- [ ] Logs and results expose only bounded content-free phase/reason/render metrics and existing
  execution/cost metadata.
- [ ] No screenshot, DOM/accessibility content, page text, cookie, prompt, reservation fact, or model
  reasoning is persisted by default.

## Dependencies

- US-165 and the `/bookings` Browser Use diagnostic lessons from US-160 through US-163.
