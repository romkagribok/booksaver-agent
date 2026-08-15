---
unit: 002-dom-resilient-browser-workflows
bolt: 048-dom-resilient-browser-workflows
stage: model
status: complete
updated: 2026-08-15T22:33:19.000Z
---

# Static Model - Server-Backed Remote Authentication

## Bounded Context

This corrective context decides whether one immutable cookie snapshot produced by a transient
`/connect` browser represents an authenticated Booking.com session. It uses only a versioned,
code-owned, read-only server contract executed in isolated contexts. Reservation DOM, page text,
screenshots, URL appearance, cookie naming, and model output are outside the success authority.
Once verified, the context hands a single-use receipt and the exact snapshot to the existing atomic
finalization boundary. Inventory discovery begins only after authentication has been committed.

## Domain Entities

| Entity | Properties | Business Rules |
|--------|------------|----------------|
| `RemoteAuthVerificationEpisode` | attempt/caller identity, contract version, expiry, baseline outcome, candidate history, terminal outcome | One transient interactive context; baseline must prove signed-out; each stable cookie snapshot is probed at most once unless a bounded transport retry applies |
| `CandidateSessionSnapshot` | canonical Booking cookies, keyed digest, observed time, source attempt | Immutable; values stay in memory/encrypted persistence only; the same snapshot must be verified and saved |
| `ServerSessionContract` | literal HTTPS host/path/method, redirect policy, signed-out response, signed-in response, size/media bounds | Code-owned and versioned; GET only; no user/model/config URL; no reservation or mutation endpoint |
| `RemoteAuthServerReceipt` | attempt, caller, contract version, keyed snapshot digest, verified/expiry times, verifier code, consumed flag | Created only after baseline plus two independent positive probes; fresh, one-use, and exact-snapshot bound |
| `RemoteAuthVerificationResult` | closed outcome, safe response class, optional receipt, retryability | Carries no URL query, headers, body, cookie material, principal, or reservation data |

## Value Objects

| Value Object | Properties | Constraints |
|--------------|------------|-------------|
| `SessionProbeOutcome` | `signed_out`, `authenticated`, `contract_changed`, `blocked_redirect`, `challenge`, `unavailable` | Only `authenticated` may contribute to a receipt; status alone is never accepted outside the complete contract |
| `SafeServerEvidence` | status class, media class, redirect class, size class, contract version | Closed enums only; content-free and safe for logs/incidents/model-free diagnosis |
| `CandidateFingerprint` | keyed HMAC of canonical cookie bytes | Never logged or persisted as diagnostic evidence; prevents snapshot substitution/replay |
| `ReceiptValidity` | issued time, expiry, one-use state | Short bounded lifetime; attempt/caller/snapshot mismatch or consumption invalidates it |

## Aggregates

| Aggregate Root | Members | Invariants |
|----------------|---------|------------|
| `RemoteAuthVerificationEpisode` | baseline, candidate fingerprints, probe results, optional receipt, terminal result | No candidate is verified before an explicit signed-out baseline; a receipt requires two fresh isolated positive probes of identical snapshot bytes; only that snapshot may enter finalization |

## Domain Events

| Event | Trigger | Payload |
|-------|---------|---------|
| `ServerVerifierBaselineEstablished` | Empty isolated context matches signed-out contract | Contract version and safe response class |
| `CandidateSessionObserved` | Stable new Booking cookie snapshot appears | Attempt-local opaque fingerprint only |
| `CandidateSessionRejected` | Probe explicitly reports signed-out | Safe outcome only; viewer remains interactive |
| `ServerAuthenticationVerified` | Two isolated probes match signed-in contract | Receipt metadata excluding digest and session material |
| `ServerContractChanged` | Stable bounded response matches neither contract | Contract version and safe response classes for maintenance incident |
| `RemoteAuthSessionFinalizing` | Fresh receipt consumes exact snapshot | Existing attempt/caller/finalization identifiers; never cookies |

## Domain Services

| Service | Operations | Dependencies |
|---------|------------|--------------|
| `BookingSessionContractVerifier` | establish negative baseline; classify candidate twice; issue receipt | Literal Booking endpoint, isolated mobile contexts, response minimizer, ephemeral HMAC key |
| `CandidateSessionPolicy` | canonicalize Booking cookies; stabilize and deduplicate snapshots; bound retries | Interactive BrowserContext cookie API and attempt deadline |
| `RemoteAuthReceiptValidator` | verify caller/attempt/contract/time/HMAC; consume once | Candidate snapshot and attempt lifecycle |
| `RemoteAuthOutcomeMapper` | map signed-out, contract, redirect, challenge, provider, cancellation, and infrastructure outcomes | Existing typed remote-auth result and incident boundary |

## Repository Interfaces

No new repository is introduced. Candidate snapshots and receipts are attempt-local and ephemeral.
Successful exact snapshots use the existing encrypted per-user session repository. Contract-change
evidence uses the existing encrypted incident lifecycle but contains only closed server-evidence
classes. Model spend is not involved in `/connect` authentication verification.

## Ubiquitous Language

| Term | Definition |
|------|------------|
| Server session contract | Versioned read-only Booking response distinction proven by both empty and authenticated contexts |
| Negative baseline | Required empty-context signed-out result that prevents contaminated or weakened verification |
| Candidate session | Immutable Booking cookie snapshot whose stable change triggers, but never itself proves, verification |
| Isolated probe | Fresh service-worker-free context holding only the candidate Booking cookies and calling one literal endpoint |
| Server receipt | Single-use code-owned authority permitting the exact verified snapshot to enter finalization |
| Contract drift | A bounded response that is neither exact signed-out nor exact signed-in evidence under the current version |

## Invariants

1. `/connect` success never depends on reservation DOM, page text, screenshots, selectors, or model
   classification. Those signals cannot create or veto a server receipt.
2. URL, status, cookie presence/name/change, and login submission are corroboration or admission
   triggers only; the complete versioned negative/positive contract is authoritative.
3. A fresh cookie-free isolated context must establish the expected signed-out response before the
   interactive viewer can produce a verifiable candidate.
4. A receipt requires two independent isolated probes of identical immutable snapshot bytes to
   match the signed-in contract; page JavaScript, cache, and service workers cannot participate.
5. The receipt is bound to attempt, caller, contract version, short lifetime, and keyed snapshot
   digest, and it can be consumed exactly once.
6. Finalization persists the exact verified snapshot. A later interactive-cookie recapture is
   forbidden, and every failure preserves the prior saved session.
7. Explicit signed-out evidence is predictable: keep the viewer open, record no incident, and make
   no model call. Stable contract drift is maintenance-required and content-free.
8. Redirects outside the exact approved Booking contract, challenges, transport limits, cancellation,
   expiry, purge/revocation, and daemon shutdown remain typed fail-closed outcomes.
9. Response bodies may be bounded and classified in memory only; bodies, headers, query strings,
   cookie values, tokens, principals, and reservation data never enter logs, incidents, or models.
10. Inventory synchronization remains a separate post-connect workflow and cannot retroactively
    define whether the login itself succeeded.
