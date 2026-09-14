---
stage: technical-design
bolt: 076-price-terminal-contract
created: 2026-09-14T20:01:15Z
status: complete
---

# Design and ADR analysis

Constrain the price terminal submission schema to exactly the current non-OBSERVED status values.
Advertise valid values in task/tool feedback, guiding incomplete evidence to no_valid_observation.
Retain runtime validation and the success-to-observation correction; complete visible offers still
pass the existing application validator and offer selection without semantic relaxation.

Record the existing bounded history diagnostic from a finally block surrounding agent.run so
cancellation cannot erase the proposed-action/error sequence. Do not print raw errors, action
arguments, page contents, credentials, model reasoning, or usage payloads. Preserve exceptions.

Tests prove schema vocabulary, rejection followed by valid termination, success submission,
interrupted-run diagnostics, privacy and cancellation propagation. Re-run the actual caller with
a frozen candidate and qualify the final image. This is a contract/observability correction within
ADR039/040/048; no new architecture, schema migration, provider, budget or ADR is required.

## Query versus offer completeness

Clarify task and corrective feedback: query completeness concerns visible property, stay dates,
occupancy and currency. Each offer independently declares its own completeness/all-in/refundability.
Submit visible offers with honest unknown/incomplete flags; existing code filters them and may
retain other valid offers. A missing query fact still requires inspection or a supported failure.
Do not override the provider's incomplete flag, infer missing facts, or permit unchanged resubmission
to masquerade as progress. Test the real action handler with a complete query and mixed offer
evidence as well as rejection of an incomplete query. No application validator change is needed.
