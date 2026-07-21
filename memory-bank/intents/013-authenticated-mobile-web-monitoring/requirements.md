---
intent: 013-authenticated-mobile-web-monitoring
phase: inception
status: complete
created: 2026-07-19T21:23:00.000Z
updated: 2026-07-19T21:23:00.000Z
---

# Requirements: Authenticated Mobile-Web Monitoring

## Intent Overview

Run every user price check in a reproducible mobile-web Playwright context backed by that user's
authenticated session. Preserve the trusted scripted journey and LLM recovery while proving and
reporting whether the extracted final total came from authenticated mobile web and whether Genius
evidence was present.

## Business Goals

| Goal | Success Metric | Priority |
|------|----------------|----------|
| Capture mobile-web/account discounts | Checks use a mobile profile and the booking owner's valid session | Must |
| Make price origin auditable | Check trace/history and alerts identify authenticated mobile source and Genius evidence | Must |
| Keep purchasing safe | Final booking remains a human action on the user's real phone | Must |

## Functional Requirements

### FR-1: Enforce a configurable mobile-web browser profile
- **Description**: Create each check context from an allowlisted Playwright device profile, defaulting to an Android-like Chromium profile suitable for the Linux VPS.
- **Acceptance Criteria**:
  - User agent, mobile viewport, screen, touch, scale factor, locale/timezone, and `is_mobile` come from one validated profile.
  - Unknown/desktop profiles are rejected for authenticated mobile monitoring.
  - Browser context is fresh and deterministic for every owner/session boundary.
- **Priority**: Must
- **Related Stories**: US-083

### FR-2: Bind each check to its owner's authenticated session
- **Description**: Resolve Intent 012's immutable session revision for the booking owner and restore it only into that check's mobile context.
- **Acceptance Criteria**:
  - Missing/revoked/replaced/foreign session resolution yields no navigation or price.
  - No global/public/owner fallback is reachable for Telegram-owned checks.
- **Priority**: Must
- **Related Stories**: US-084

### FR-3: Verify authentication and classify Genius evidence
- **Description**: Verify rendered logged-in context before accepting a price and classify Genius evidence as `applied_or_present`, `not_observed`, or `indeterminate`.
- **Acceptance Criteria**:
  - Signed-out or indeterminate authentication/pricing fails closed and invalidates the exact session revision when appropriate.
  - Authenticated plus `not_observed` is valid because not every property/rate participates.
  - A Genius claim is emitted only when page/rate evidence supports it.
- **Priority**: Must
- **Related Stories**: US-085

### FR-4: Preserve the trusted price journey and bounded LLM escalation
- **Description**: Run direct trusted search-results navigation, exact property selection, context verification, semantic offer extraction, equivalence/refundability gates, and bounded LLM recovery inside the mobile context.
- **Acceptance Criteria**:
  - Homepage form remains skipped and result-card headline prices remain non-authoritative.
  - Existing action guard continues blocking reserve/checkout/payment/cancel actions.
  - Mobile layout changes may invoke the same bounded LLM recovery without bypassing context verification.
- **Priority**: Must
- **Related Stories**: US-086

### FR-5: Persist and display price-source provenance
- **Description**: Attach durable, non-secret provenance to every success/failure: device profile, mobile-web channel, session revision identifier, authentication validation, Genius evidence, and observed timestamp.
- **Acceptance Criteria**:
  - Check history/trace and savings alerts distinguish authenticated mobile web from public/unknown sources.
  - Provenance contains no cookies, account identifiers, query `sid`, or secret storage state.
  - A successful Money result cannot exist without complete validated provenance.
- **Priority**: Must
- **Related Stories**: US-087

### FR-6: Preserve real-device rebooking boundaries
- **Description**: Monitoring may navigate/read mobile web, but the final reserve/cancel/payment action remains on the user's real phone.
- **Acceptance Criteria**:
  - Telegram handoff warns the user to be signed into the same Booking.com account and to confirm final total/refundability.
  - VPS/browser automation never performs the irreversible final action.
  - Native-app automation and guaranteed app-only prices are explicitly not claimed.
- **Priority**: Must
- **Related Stories**: US-088

## Non-Functional Requirements

### Reliability and Performance
- The default mobile profile must work in the current Docker/Chromium VPS image without another browser dependency.
- Mobile configuration adds no extra Booking.com request path; checks remain serialized and bounded by existing caps.

### Security and Observability
- Provenance is durable but contains only non-secret identifiers/evidence.
- Screenshot/trace redaction and the action guard remain unchanged or stronger.

### Verification
- Tests cover profile validation/application, authenticated binding, Genius tri-state classification,
  mobile DOM/LLM paths, provenance persistence/rendering, real-device handoff wording, and full regression.

## Constraints

- Depends on Intent 012's per-user encrypted session contract.
- Playwright mobile web is emulation, not a physical phone or native Booking.com app.
- No additional concurrent browser path, official Booking.com API, or autonomous purchase.

## Assumptions and Decisions

- Booking.com may make mobile rates available to mobile browsers; app-only promotions cannot be guaranteed.
- Android-like Chromium is the operational default; other allowlisted mobile profiles are optional.
- The product owner authorized inception and DDD stages through Test; closure/commit/push/deploy await final review.

## Scope Exclusions

- Android emulator/Appium, native app inspection, app-only price guarantees, and automated checkout.
