---
id: ADR-042
title: Admit Booking-required AWS WAF token bootstrap subresources
status: accepted
created: 2026-08-31T23:20:00Z
bolt: 062-agentic-inventory-executor
---

# ADR-042: Admit Booking-Required AWS WAF Token Bootstrap Subresources

## Context

The authenticated Booking.com trips document returned a valid browser bootstrap, but its rendered
page remained blank because the BookSaver network guard rejected three HTTPS subresource requests
to randomized subdomains of `token.awswaf.com`. Direct Playwright comparison and content-free CDP
diagnostics proved that Booking's current application requires those AWS WAF token requests before
it renders the trip groups. Blocking them made both Browser Use semantic state and screenshots
empty, so no browser harness could perceive the account.

The accepted egress boundary named Booking.com application/static hosts, Anthropic, and loopback.
AWS WAF token delivery is therefore a real, narrow architecture exception rather than a hidden
implementation detail.

## Decision

Permit only HTTPS port 443 subresource requests to proper subdomains of `token.awswaf.com` during
the transient Browser Use episode. Do not permit the bare domain, HTTP, credentials in URLs, custom
ports, or lookalike suffixes. Keep `token.awswaf.com` outside the observable-destination and action
guards, so the agent cannot navigate to or interact with it.

Booking-domain cookies remain scoped to Booking domains and are not sent to the unrelated AWS WAF
domain. BookSaver records only the bounded hostname when diagnosing a rejected request and never
persists request URLs, query values, response bodies, screenshots, or page content.

## Rationale

- The exception restores the provider's required browser bootstrap without adding an agent action
  or arbitrary web authority.
- A suffix plus HTTPS/port/credential check tolerates randomized regional token hostnames while
  rejecting the bare host and suffix-confusion lookalikes.
- Keeping observation and interaction admission Booking-only preserves ADR-040 and ADR-041.

## Alternatives Considered

- **Continue blocking the token host**: rejected because the protected trips page stays visually
  blank and inventory discovery is impossible.
- **Allow all AWS domains or all HTTPS subresources**: rejected because it materially broadens
  authenticated egress without evidence of need.
- **Encode the current randomized full hostname**: rejected because the hostname is deployment and
  challenge specific, recreating the provider-churn failure this migration is meant to reduce.

## Consequences

- Exact-container egress tests must cover allowed randomized subdomains and rejected bare,
  insecure, and suffix-confusion destinations.
- If Booking changes its WAF provider, the page will fail closed with content-free readiness and
  blocked-host diagnostics until a separately reviewed exception is accepted.
