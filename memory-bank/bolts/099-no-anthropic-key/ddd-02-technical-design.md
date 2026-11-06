---
unit: 002-no-anthropic-key
bolt: 099-no-anthropic-key
stage: design
status: complete
created: 2026-11-06T00:27:55Z
updated: 2026-11-06T00:27:55Z
---

# Technical Design - No Anthropic Key

- `resolve_execution_route`: in `consented_users`, an active invitee routes to the configured
  method whatever their disclosure record. `_uses_agentic_inventory`: every active user.
- Inform once: after a scheduled slot, `_inform_provider_change(user_id)` sends one Telegram message
  to an invitee with a ready session whose disclosure record differs from the configured version,
  then records the configured version. Failures are logged and retried next slot.
- Disclosure: default `disclosure_version` becomes `typesafe-visible-booking-page-v1`; the `/connect`
  text names TypeSafe's Jev.
- Discovery: when the grouped reader does not handle the page, the executor returns a provider
  failure instead of starting the Browser Use agent; `BrowserUseInventoryBrowserExecutor` and
  `LocalBrowserUseInventoryExecutor` no longer require an API key; the CLI always builds them.
- Deploy: production config gets the new `disclosure_version`; after release the key is removed from
  `.env` and the owner revokes it.

## Test Plan

Routing for invitees with and without a record; inform-once (sent once, recorded, retried after a
failed send, never to the owner, not without a session); discovery without a key and with an
unreadable trip list; daemon and CLI start without the key; staging on both accounts.
