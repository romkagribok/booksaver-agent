---
stage: plan
bolt: 029-direct-booking-auth-only
created: 2026-07-26T19:45:19.000Z
---

## Implementation Plan: Direct Booking Authentication Only

### Objective

Prevent the transient Telegram remote-auth browser from loading external provider pages and make
direct Booking.com email/password login the explicit supported path.

### Deliverables

- A Booking.com-specific navigation hostname predicate with exact/subdomain matching.
- Context-level blocking for external same-tab, child-frame, and popup navigation before the first
  page opens.
- Preserved cross-origin non-navigation resources needed by Booking.com direct login.
- Updated Telegram launch and viewer-ready guidance.
- Targeted host-boundary, provider, resource, command, callback, and viewer-message tests.

### Dependencies

- `SystemRemoteBrowserRunner._secure_context`: existing request-routing enforcement point.
- `RemoteAuthenticationManager._viewer_message`: BookSaver-owned live viewer status.
- Telegram `/connect` launch flow: BookSaver-owned pre-browser guidance.

### Technical Approach

Replace the current Booking/Google/Apple top-level allowlist with an exact Booking.com ownership
predicate. Abort every non-Booking document navigation, including child frames and popup main
frames, using `blockedbyclient`. Continue cross-origin non-navigation subresources so Booking.com's
third-party scripts, images, and anti-abuse dependencies remain available.

Update stable BookSaver-owned messages rather than injecting layout-specific selectors or scripts
into Booking.com. State that users must use Booking.com email/password, external providers are
disabled, and passwords must never be sent in Telegram chat.

### Acceptance Criteria

- [ ] Exact `booking.com` and its subdomains can navigate top-level.
- [ ] Google, Apple, Microsoft, Facebook, arbitrary hosts, and lookalike Booking hosts are blocked.
- [ ] Popup and child-frame provider pages are covered by the context-level policy.
- [ ] External non-navigation resources continue as before.
- [ ] Typed `/connect`, reconnect callback, and live viewer status carry direct-login guidance.
- [ ] Existing terminal messages, timeout, cancellation, and secret boundaries remain unchanged.
