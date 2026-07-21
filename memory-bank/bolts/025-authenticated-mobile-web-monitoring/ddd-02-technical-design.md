---
stage: design
bolt: 025-authenticated-mobile-web-monitoring
created: 2026-07-19T21:23:00Z
---

# Technical Design: Authenticated Mobile-Web Monitoring

## Architecture

Extend the existing single serialized monitor path. Browser startup/context creation takes a validated
mobile profile and Intent 012 snapshot; the journey adds rendered auth/Genius evidence; result,
persistence, alerts, and CLI trace carry a small provenance value object.

## Configuration and Browser Context

- Add `[browser] device_profile = "Pixel 7"` (or an internally stable allowlisted alias) with an
  Android-like Chromium default. Locale/timezone remain explicit configuration.
- Build context options from Playwright's device descriptor: UA, viewport, screen, touch,
  device-scale, and mobile behavior. Reject nonallowlisted/desktop profiles at config validation.
- Restore exactly one owner snapshot into a newly created context; close it after the check.

## Verification

- After trusted results/property navigation, use stable account/sign-in semantic evidence to classify
  authentication. Signed-out/ambiguous results become `AUTH_REQUIRED`, never a price.
- Inspect the selected rate/property semantics for Genius labels/discount evidence. Record tri-state;
  do not infer eligibility solely from price or account login.
- Mobile context verification complements—not replaces—URL date/occupancy and equivalent refundable
  offer verification.

## Provenance

- Value object: channel=`authenticated_mobile_web`, profile alias, session revision ID,
  auth=`validated`, Genius tri-state, observed UTC timestamp.
- Persist with check history using an additive schema migration or a normalized JSON/text column;
  include in check trace and success/failure rendering. Never store cookies, account data, `sid`, or URL
  tracking parameters.
- Savings alerts label authenticated mobile web and only say Genius when evidence is present.

## Safe Handoff

Telegram rebook handoff copy instructs the user to open on a real phone, sign into the same account,
and verify final all-in/refundable terms. Existing deep-link and post-rebook actual-total flow remain.

## Test Design

- Config/device descriptor application; fresh-context isolation; owner snapshot binding; auth evidence
  signed-in/signed-out/ambiguous; Genius tri-state; mobile semantic DOM and LLM escalation; provenance
  persistence/redaction/rendering; no extra request path; action guard; phone-handoff copy; full suite.
