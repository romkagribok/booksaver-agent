---
id: 002-classify-current-page-with-llm-fallback
unit: 002-dom-resilient-browser-workflows
intent: 022-adaptive-booking-browser-resilience
status: complete
priority: must
created: 2026-08-13T01:59:59.000Z
assigned_bolt: 042-dom-resilient-browser-workflows
implemented: true
---

# Story: Classify the Current Page with LLM Fallback

## User Story

**As a** BookSaver user with a saved Booking.com session
**I want** changed login and account-page DOM classified correctly
**So that** I receive reconnect guidance instead of repeated generic inventory failures

## Acceptance Criteria

- [ ] **Given** a changed login page still exposes a weak reservations/header link, **When** fresh
  page state is assessed, **Then** login/MFA evidence outranks the weak signed-in marker and the
  session is not accepted as authenticated.
- [ ] **Given** strong deterministic evidence confirms authentication required, MFA, captcha, bot
  wall, external, or prohibited state, **When** classification completes, **Then** the exact reason
  returns immediately with zero LLM calls.
- [ ] **Given** deterministic current-page state is ambiguous, **When** Sonnet classification is
  valid and confident, **Then** code maps only its allowlisted class/evidence/action and performs no
  model-proposed action on a protected page.
- [ ] **Given** Sonnet classification is invalid or remains unknown, **When** Opus remains eligible,
  **Then** Opus performs the bounded classification/diagnosis under Unit 1 policy.
- [ ] **Given** either model returns `authentication_required`, **When** inventory/search/auth-capture
  outcome maps through the coordinator, **Then** the caller session becomes reauth-required and
  Telegram recommends `/connect`.
- [ ] **Given** a model returns `authenticated`, **When** no code-verified authenticated workflow has
  completed, **Then** BookSaver may enter guarded read-only recovery but cannot save or extend the
  session solely from that classification.
- [ ] **Given** page observation/provider/budget is unavailable, **When** classification terminates,
  **Then** the exact non-DOM reason is preserved instead of claiming authentication or DOM drift.

## Technical Notes

- Replace the boolean selector heuristic with a typed protected-state-first assessment.
- Preserve fresh post-failure evidence; stale `about:blank` remains only a progress baseline.
- Apply the same typed result in Playwright session validation, remote-auth capture, inventory, and
  search postflight checks.

## Dependencies

### Requires

- US-130, US-131, and US-133.

### Enables

- US-135, US-136, and correct reconnect incident behavior.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Login and account markers coexist | Protected/login evidence wins or state remains ambiguous |
| Captcha inside authenticated chrome | Deterministically classify bot wall when conclusive; zero model calls/actions |
| Model confidently says authenticated but verifier disagrees | Verifier wins; no session refresh |
| Current page is external | Block before any recovery action |

## Out of Scope

- Model entry of credentials, login submission, MFA, or captcha solving.
- Using model confidence as inventory-completeness evidence.
