---
stage: model
bolt: 024-per-user-booking-sessions
created: 2026-07-19T21:23:00Z
---

# Domain Model: Per-User Booking.com Sessions

## Ubiquitous Language

- **Session owner**: Stable local user whose Booking.com state may serve only that user's bookings.
- **Session revision**: Opaque identity for one imported/refreshed encrypted browser-state version.
- **Session health**: `missing`, `ready`, `expired`, `reauth-required`, or `invalid`.
- **Authenticated-required policy**: A check without proven owner authentication yields no price.
- **Isolation boundary**: Clean browser context plus exactly one owner session revision.

## Entities and Value Objects

- **UserBookingSession** (aggregate root): owner ID, platform, revision ID, encrypted payload reference,
  health, imported/validated/expiry timestamps. Exactly one current revision per owner/platform.
- **SessionSnapshot**: Immutable decrypted state plus revision; exists only in memory.
- **SessionResolution**: Ready snapshot or typed unavailable reason; never contains another owner.
- **SessionValidation**: revision, authenticated boolean, observed timestamp, reason.

## Invariants

1. Owner identity and active access are checked at import, resolution, refresh, and invalidation.
2. Decrypted cookie/storage state never crosses into logs, traces, SQLite, Telegram, or domain errors.
3. Resolution cannot fall back to global, owner, foreign, or public state.
4. Restore always targets a clean browser context.
5. Compare-and-replace refresh cannot overwrite a newer import.
6. Auth-unavailable checks produce no live Money or savings opportunity.

## Domain Services and Repository Contracts

- **SessionImportService**: normalize → validate target → encrypt → atomic replace.
- **AuthenticatedSessionProvider**: `resolve(user_id, platform) -> SessionResolution`.
- **SessionLifecycleService**: validate/refresh/invalidate/delete by owner and revision.
- **PerUserSessionRepository**: save/load/status/delete/compare-and-replace without plaintext storage.

## Domain Events

- Session imported/replaced, validated, reauth-required, expired, deleted. Payload is redacted and
  contains owner/revision/health only.

## Story Coverage

All aggregates, invariants, and services map to US-077 through US-082.
