---
intent: 010-telegram-privacy-boundaries
created: 2026-07-19T02:50:44Z
updated: 2026-09-03T23:40:07Z
status: construction
---

# Telegram Privacy Matrix

This matrix is the maintained regression contract for every Telegram-facing data or action family.
“Exact” means booking-derived identifiers, properties, dates, rooms, prices, outcomes, failures,
savings, traces, rebook state, or user-supplied secret material.

| Surface | Data/action | Required gate | Foreign/revoked/non-private behavior |
|---------|-------------|---------------|--------------------------------------|
| `/start`, `/help` | Safe command catalog; invite redemption may mutate access | Private chat, then fixed invite access | Generic refusal; non-private cannot redeem |
| `/status` | Daemon health + caller active-booking count | Private, active caller scope | No global/exact enumeration |
| `/bookings` | Caller booking exact data | Private, active caller + owned query | Empty/not-recognized without foreign data |
| `/checks`, `checks:` | Caller check history | Private, active caller + owned booking resolver | Foreign equals missing; no check content |
| `/savings` | Caller savings exact data | Private, active caller + owned query | No foreign opportunity content |
| `/checknow`, `checknow:` | Caller booking picker, browser request, completion | Private, active caller + owned booking at admission/work/completion | No browser for foreign/queued-revoked; no post-revoke detail |
| `/register` dialog | New caller-owned booking; confirmation may be globally unique | Private, active caller at start/save | Non-private no dialog; foreign conflict masked |
| `/editbooking`, `bedit:` | Caller booking mutation | Private, active caller + owned resolver at selection/save | Foreign equals missing; conflict masked |
| `/deletebooking`, `bdel:` | Caller booking deletion | Private, active caller + owned resolver at selection/confirm | Foreign equals missing; no mutation |
| `/rebook`, `rebook:select:` | Caller opportunity and guided session | Private, active caller + owned opportunity at start and every wait/handoff/reply | Foreign equals missing; revoked session terminates boundedly |
| Rebook confirmation callbacks | One pending caller prompt | Private, active callback + nonce/chat/user match | Always acknowledged; no state advance |
| `/setkey`, `/deletekey`, key dialog | Caller secret validation/storage/deletion | Private, active caller before dialog/key handler | No validation, deletion, or storage |
| `/admin users` | Allowlisted identity/access/counts + Browser Use owner-funding policy + boolean personal legacy-key presence | Private owner + aggregate projection | Owner-only; key representations and exact repositories forbidden |
| Admin invite/revoke/purge callbacks | Identity/access mutation only | Private owner + internal user ID | Owner-only; no exact records |
| Scheduled queue | Browser/LLM check and local results | Current active owner immediately before allowance/work | Newly revoked item skipped without cap record |
| Savings alert | Caller savings exact data | Active booking owner at delivery | Drop; never fallback to another user |
| Check-cap/key notices | Usage/key state notice | Current active target at delivery | Drop after revocation |
| Immediate completion | Caller check result | Current active owner at work, pipeline, and completion | Local result may persist; external disclosure suppressed |

## Test Sentinels

Two-user tests use unique, non-overlapping markers for property names, confirmation IDs, booking IDs,
check IDs, prices/currencies, failure details, and savings IDs. Each adapter-family assertion checks
both that the caller's own marker can appear where allowed and that every foreign marker is absent.
Admin tests additionally fail if an exact-record repository method is called at all.
The funding projection also seeds recognizable encrypted-key sentinels and permits only a boolean
configured/not-configured label; key bytes, fragments, fingerprints, hashes, and validation state
must remain absent.

## Threat-Model Boundary

This matrix proves isolation between bot users through Telegram. It does not hide local data from the
VPS/root operator or claim end-to-end secrecy from Telegram, Booking.com, or the configured LLM
provider where established product flows necessarily send data.
