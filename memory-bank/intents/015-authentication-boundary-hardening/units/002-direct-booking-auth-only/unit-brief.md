---
unit: 002-direct-booking-auth-only
intent: 015-authentication-boundary-hardening
phase: inception
status: complete
unit_type: cli
default_bolt_type: simple-construction-bolt
created: 2026-07-26T19:41:07.000Z
updated: 2026-07-26T19:41:07.000Z
---

# Unit Brief: Direct Booking Authentication Only

## Purpose

Keep the transient `/connect` browser on Booking.com-owned interactive pages and make the supported
direct-login path explicit.

## Scope

### In Scope

- Context-level main-page, child-frame, and popup hostname enforcement.
- Booking.com exact/subdomain matching and spoof rejection.
- Telegram launch and ready/connected viewer guidance.
- Regression coverage for navigation and messaging.

### Out of Scope

- Layout-specific hiding of provider buttons.
- Blocking cross-origin scripts, images, or other non-navigation resources required by Booking.com.
- Bypassing provider security controls or native Booking.com application automation.

## Assigned Requirements

| FR | Requirement | Priority |
|----|-------------|----------|
| FR-2 | Restrict interactive login to Booking.com | Must |
| FR-3 | Explain direct-login-only behavior | Must |

## Domain Concepts

- **Interactive navigation**: main-frame, child-frame, or popup document navigation.
- **Booking-owned host**: exact `booking.com` or a dot-delimited subdomain.
- **Direct-login guidance**: safe text shown before and while the remote browser is active.

## Story Summary

| Story ID | Title | Priority | Status |
|----------|-------|----------|--------|
| US-099 | Block external identity-provider navigation | Must | Complete |
| US-100 | Guide users to direct Booking.com login | Must | Complete |

## Dependencies

- Completed Bolt 026 remote-authentication gateway.
- Completed Bolt 027 remote-auth display reliability.

## Constraints

- The route boundary is installed before creating the first page and automatically covers popups.
- Direct Booking.com email/password and Booking-owned verification flows remain usable.
- Messages never request credentials in Telegram or reveal sensitive runtime state.

## Success Criteria

- [x] Booking.com exact/subdomain pages load and all external provider documents are blocked.
- [x] Spoofed Booking hostnames remain blocked.
- [x] Telegram and viewer messages clearly state direct-login-only behavior.
- [x] Targeted and full quality gates pass.

## Bolt Suggestions

| Bolt | Type | Stories | Objective |
|------|------|---------|-----------|
| 029-direct-booking-auth-only | Simple | US-099, US-100 | Enforce and explain direct Booking.com authentication |
