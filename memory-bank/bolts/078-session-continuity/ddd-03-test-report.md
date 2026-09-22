---
stage: test
bolt: 078-session-continuity
created: "2026-09-20T20:19:17Z"
status: complete
---

# Session continuity verification

Local implementation is ready for integrated and exact-image qualification. This report does
not claim production session renewal, native Telegram acceptance, or Linux cleanup acceptance.

## Local evidence

- 162 coordinator, encrypted repository, service, Telegram and CLI tests passed together.
- The subsequent coordinator and Telegram selection passed 31 tests, including the additional
  uncertainty-notice wording regression. These counts overlap and are not additive.
- The browser track passed 294 affected tests; one real detached-child Linux test was skipped
  on the local macOS host. Browser-track Ruff and mypy passed.
- Whole-source Ruff passed; mypy passed all 125 source files.
- AI-DLC artifact validation reported zero errors (historical warnings remain).

Regressions cover exact caller selection without bookings; durable daily and retry scheduling;
legacy ACTIVE expiry recovery versus explicit EXPIRED/REQUIRES_REAUTH; owner migration retaining
old expiry until proof; new login, disconnect, purge and access-revocation races; foreground
success invalidating old attempts; once-per-revision notices; 48-hour uncertainty wording;
31 consecutive daily verifications without invented monthly/cookie expiry; unsupported-platform
silence; and fatal cleanup setting daemon stop before releasing the shared gate. Browser tests
exercise exact snapshot proof, temporary-response classification, pre-desktop mobile capture,
worker ownership and PID reuse safety.

## Pending release evidence

The parent owns the full suite, final review, exact Linux candidate-image smoke (including
actual Chromium and detached-child timeout cleanup), notifications-disabled cloned-caller
maintenance replay, restart/daily suppression, and production promotion checks. No live account
was touched by this implementation track. Provider revocation remains possible at any time;
local 31-day simulation is not a promise of a month's server validity.

## 2026-09-20T20:24:46Z — integrated construction gate

Final combined source passed **2,949 tests**, with one Linux-only cleanup test skipped on macOS,
52 existing warnings, in 68.54 seconds. Ruff and mypy (125 modules) passed. All 16 AI-DLC validator
tests passed; artifact/status validation had zero errors/inconsistencies. The prior full run found
three stale safety-test host fixtures; adding the new optional verified-session field retained all
dialog/tab/navigation rejection assertions, and the 73-test traversal selection passed before the
final full run. Exact combined-image Dev/Staging, current-head Bugbot and production remain separate
Operations gates. Unicode paste is an explicit unsupported-character rejection, not full-Unicode
acceptance; no physical Telegram test is claimed. User approved scoped completion through release.

## 2026-09-22T00:08:33Z — pre-release review corrections

An independent pre-release source review of the combined branch confirmed two notice defects.
First, a verified renewal carried `notice_sent_at` forward, so a session that had received the
48-hour unverified notice and later recovered could be signed out by Booking.com without any
reconnect request on that revision. A fresh server proof now clears the notice claim, so a later
confirmed sign-out produces exactly one notice. Second, the check-time reconnect prompt required a
session revision, silently dropping users whose bundle is missing or undecryptable; those users
again receive the direct reconnect prompt under the notifier's existing 24-hour cooldown.

Two regressions cover unverified-notice → renewal → sign-out (one notice each) and missing or
corrupt bundles. Deliberate design points were reviewed and left unchanged: unconfirmed owned
worker cleanup stops the daemon by approved design, and the uncertainty notice is evaluated on
the first completion at or after 48 hours of failure, which the retry ladder places at roughly
55 hours. Full gate after the fix: **2,952 tests passed**, one Linux-only skip, Ruff and mypy
(125 modules) clean, AI-DLC validator zero inconsistencies. Exact-image Dev/Staging and
promotion for the corrected head remain Operations gates.
