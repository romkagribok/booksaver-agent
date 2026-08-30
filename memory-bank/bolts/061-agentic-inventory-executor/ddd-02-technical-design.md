---
stage: design
bolt: 061-agentic-inventory-executor
created: 2026-08-30T22:30:00Z
---

# Technical Design: Canonical HTTPS Browser Use Inventory Entry

## Architecture Pattern

Keep the provider-neutral port and trigger-specific adapter from ADR-041. Introduce one private
Browser Use entry constant in its infrastructure module and navigate to it directly. Do not change
the shared Stagehand `INVENTORY_ENTRY_URL` or any control-plane contract.

## Layer Structure

- **Domain/application/coordinator**: No change.
- **Browser Use adapter**: Own the canonical HTTPS `mytrips` literal and use it for the initial
  code-owned navigation before agent construction. When a fully inspected safe anchor declares
  `target=_blank`, resolve its guarded HTTPS href and replay it in the existing tab rather than
  dispatching a popup-producing click. Ignore aggregate meaningful text on non-interactive
  structural ancestors while continuing to inspect all ancestor roles and attributes. Count a
  rejected proposal against the action limit and return a successful content-free guard outcome
  without replay. Browser Use 0.11.13 reserves `success=True` for terminal `is_done=True` results,
  so continued actions omit that flag and carry only bounded extracted content.
- **Network guard**: No change; HTTP remains rejected.

## Security Design

- The literal is HTTPS, exact-hosted at `secure.booking.com`, and has no query or fragment.
- Redirects and page/model content never select the initial destination.
- Do not permit HTTP, disable Fetch interception, or broaden action/destination allowlists.
- Same-tab normalization occurs only after the existing node/ancestor, label, attribute, href,
  host, route, and current-page checks and is followed by the existing post-action check.
- App-install/download destinations remain prohibited. A denied pre-action proposal never reaches
  the browser; mutation, dialog, extra-target, and post-destination violations still fail closed.

## Reliability Design

Bypass the obsolete entry that currently redirects to HTTP. Production evidence proves direct
HTTPS `mytrips` reaches the authenticated page. Browser Use meaningful text on a structural footer
contained 1,231 unrelated characters, so structural containers cannot be treated as interactive
labels. The first real agent choice also followed an irrelevant app-install footer route; explicit
task steering plus bounded pre-action correction lets the harness recover without expanding action
authority. When no relevant control is visible, the task directs the agent to scroll rather than
sample unrelated links. Disable Browser Use's explicit thinking response field for this one-action
typed loop; private provider inference remains provider-owned, while the harness requests only the
bounded structured action needed for the next step. On a missing observation, log only step count,
closed-registry action names, and bounded error categories.
The provider-facing reservation action normalizes scalar JSON values and discards unknown keys so
ordinary model formatting does not consume harness retries; if optional date/money/evidence fields
still cannot be mapped, preserve only bounded identity facts and downgrade the rest to unknown.
The trusted application validator and safe persistence merge remain authoritative for acceptance
and eligibility. After current upcoming positives are submitted, request an immediate honest
partial `done` instead of spending the remaining deadline trying to prove account completeness.
For positive results, derive only an incomplete scope/count record from accepted reservation
submissions; malformed, duplicate, or overconfident model scope claims are ignored and cannot grant
absence-reconciliation authority.
The provider-facing reservation action normalizes scalar JSON values and discards unknown keys so
ordinary model formatting does not consume harness retries; the trusted mapping/validator still
rejects missing identity, invalid scope, ambiguous money, dates, lifecycle, or eligibility facts.
After current upcoming positives are submitted, request an immediate honest partial `done` instead
of spending the remaining deadline trying to prove account completeness.

## Test Design

- Assert the Browser Use-specific entry is exact HTTPS `mytrips` and differs from the shared
  Stagehand legacy entry.
- Assert the observed HTTP `mytrips` URL remains rejected by `_browser_request_allowed`.
- Assert large structural ancestor text does not reject an otherwise guarded interactive link,
  clicks with no interactive ancestor remain denied, app-install routes remain denied, and guard
  reason logging contains no labels, URLs, or attributes.
- Assert continued results match the qualified 0.11.13 contract and history diagnostics cannot
  include tool parameters, page content, model thoughts, URLs, or provider error text.
- Assert provider scalar/null/extra formatting is normalized, malformed optional facts become
  unknown, and stable identity remains mandatory before trusted validation.
- Assert a valid positive with malformed scope claims produces only code-owned incomplete coverage
  and cannot archive unseen reservations.
- Assert provider scalar/null/extra formatting is normalized before tool dispatch while trusted
  observation validation remains unchanged.
- Run the focused Browser Use/coordinator suite, repository quality gates, exact candidate image,
  and bounded authenticated VPS replay.

## ADR Analysis

No new ADR is required. This is a corrective implementation of ADR-041's code-owned HTTPS entry
and egress confinement, not a new architecture or trust decision.
