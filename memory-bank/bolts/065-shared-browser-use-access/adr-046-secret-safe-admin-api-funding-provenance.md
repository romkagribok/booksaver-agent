---
id: ADR-046
title: Secret-safe admin API funding provenance
status: accepted
created: 2026-09-03T23:39:00Z
bolt: 065-shared-browser-use-access
---

# ADR-046: Secret-Safe Admin API Funding Provenance

## Context

The owner pays for every agentic Browser Use call through `BOOKSAVER_LLM_API_KEY`, including work
triggered by invited users. `/admin users` currently shows per-user usage counts but cannot explain
who funds those calls. Optional encrypted personal keys still exist for legacy LLM paths, which can
make the current display misleading.

Intent 010 deliberately prohibited all personal-key state in Telegram administration to minimize
cross-user information. The self-hosting owner is already the trusted host administrator and key
custodian, and now needs coarse operational funding visibility. Returning any key bytes, fragments,
fingerprints, validation state, or exact historical attribution would exceed that need.

## Decision

Narrowly amend the owner-only aggregate admin projection to expose two current-policy facts per
user:

- `Browser Use=deployment owner`, meaning future agentic Browser Use calls use the deployment
  owner's environment key.
- `personal legacy key=configured|not configured`, meaning only whether encrypted key bytes exist
  for legacy LLM paths.

Derive personal-key presence inside the existing aggregate SQL with `encrypted_key IS NOT NULL` and
return only a boolean. Do not select the blob into the projection, invoke the key store, decrypt,
hash, fingerprint, validate, prefix, suffix, or otherwise transform a key. Keep the projection
owner-only, aggregate-only, and independent of runtime counter availability.

Do not claim historical per-key billing attribution because existing cost attempts persist caller
identity and costs but not key provenance. Browser Use continues to ignore personal keys until a
separate architecture is accepted.

## Alternatives Considered

- **Show masked key suffixes or fingerprints**: rejected because they create correlatable secret
  identifiers without improving the funding decision.
- **Decrypt keys to identify their provider account**: rejected because administration has no need
  to handle plaintext and provider ownership is not locally provable.
- **Show only Browser Use owner funding**: rejected because the owner also asked whether each user
  has a personal key configured, and a boolean satisfies that need safely.
- **Add historical per-key cost totals**: deferred because the ledger does not persist trustworthy
  key provenance and retroactive inference would be inaccurate.
- **Expose the information to each invited user**: deferred; this story concerns the owner-only
  operational dashboard.

## Consequences

### Positive

- The owner can see that invited Browser Use traffic consumes the owner's API budget.
- Optional personal-key presence is clear without exposing any key representation.
- No migration, provider call, or decryption path is added.
- Existing exact-record privacy boundaries remain intact.

### Negative

- Coarse personal-key presence is now visible in Telegram to the owner, narrowing Intent 010's
  earlier omission policy.
- The label describes current policy and cannot answer which key funded an old legacy attempt.
- Future Browser Use BYOK support will require updating this projection and a separate decision.

## Relationship to Existing Decisions

- **ADR-019 preserved**: personal keys remain Fernet-encrypted at rest and plaintext never enters
  logs or admin output.
- **Intent 010 FR-3/US-069 amended**: coarse boolean key presence and code-owned funding policy are
  now allowed only in the owner aggregate; all actual key representations and exact user data remain
  forbidden.
- **ADR-031 preserved**: cost admission and reconciliation remain unchanged.
- **ADR-043 clarified**: the Browser Use adapter uses the deployment owner's environment key for
  every caller.

## Validation

- Repository tests prove only a boolean is returned for null/non-null encrypted keys.
- Telegram sentinel tests prove recognizable ciphertext and every exact booking/check field remain
  absent while the two allowed labels are present.
- Non-owner refusal and runtime-usage-unavailable tests remain active.
- Static review confirms no key store or decrypt call is reachable from admin projection code.
