---
bolt: 042-dom-resilient-browser-workflows
created: 2026-08-13T02:39:01Z
status: accepted
superseded_by:
---

# ADR-032: Protected-First Page State and Exhaustive DOM Step Registry

## Context

BookSaver currently spreads DOM assumptions across Playwright authentication helpers, remote-auth
polling, inventory navigation, browser recovery, and price search. A weak signed-in heuristic can
accept a changed login page because header/Genius/bookings chrome remains visible. Separately, an
LLM's correct `authentication_required` conclusion is collapsed through `gave_up` into generic
`navigation_failed`, so the session is not marked for reconnect. Missing selector evidence can also
be mislabeled as a proven business outcome.

## Decision

1. Register every production DOM-sensitive step under a stable typed definition containing its
   deterministic postcondition, safe capabilities, protected states, semantic schema/recovery mode,
   and complete terminal mappings.
2. Classify every fresh page using protected-state precedence. Observation loss, external or
   prohibited destinations, captcha/bot wall, MFA/security challenge, and credential/login evidence
   outrank weak account chrome and terminate under exact known codes without a model call.
3. Treat weak signed-in markers as inconclusive. Authentication is verified only by strong supported
   account/inventory evidence or a fixed guarded read-only probe.
4. Use Bolt 041's Sonnet-first, Opus-on-quality-failure session only for genuinely ambiguous state.
   The classifier returns typed advisory facts and never browser actions.
5. Never save/refresh cookies, extend a session, or prove account identity from a model-authenticated
   classification alone.
6. Centralize exact mapping so authentication, MFA, captcha, provider, observation, budget, safety,
   and unresolved ambiguity survive inventory/search/coordinator layers without generic fallthrough.
7. Require an executable structural coverage test: adding a production DOM step without a complete
   registry definition fails the suite.

## Rationale

Protected-first classification fixes the current reconnect failure and preserves the existing
human-only security boundary. An explicit registry makes future DOM-sensitive seams visible and
testable. Typed model classification gives changed layouts a recovery path without granting an
untrusted model authority over authentication, browser actions, or booking truth.

## Consequences

### Positive

- Changed login DOM cannot be mistaken for a valid session from weak chrome.
- Predictable failures such as `/connect` required remain precise, cheap, and deterministic.
- Genuine ambiguity can use the stronger model path without duplicating budgets or credentials.
- New DOM-sensitive workflow changes must declare their recovery and terminal semantics.

### Negative

- Existing browser/auth/inventory/search code must adopt typed classifications and mappings.
- Some previously permissive signed-in heuristics become conservative and may require `/connect`
  until strong evidence is available.
- The registry adds explicit maintenance whenever production workflow steps change.

### Risks and Mitigations

- **False protected classification**: bounded deterministic evidence and model candidate states keep
  uncertainty explicit; no model may override conclusive code evidence.
- **Repeated classification spend**: debounce/cache only a stable ambiguous fingerprint within one
  remote-auth episode and share the Bolt 041 job budget.
- **Registry drift**: production journeys export their exact step declarations and structural tests
  compare them with registry membership.
- **Privacy leakage**: classifications store only allowlisted categories/references; possible login
  pages exclude screenshots and typed values.

## Related

- **Stories**: US-133, US-134, US-135, US-136
- **ADRs**: ADR-015, ADR-016, ADR-019, ADR-024, ADR-026, ADR-027, ADR-030, ADR-031
