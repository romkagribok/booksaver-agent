---
intent: 025-session-continuity-and-paste
phase: operations
status: complete
created: "2026-09-20T19:54:17Z"
updated: "2026-09-22T01:42:44Z"
---

# Session continuity and remote login paste

## Request and checkpoint

The user requests automatic background cookie renewal without repeated reconnect nudges, aiming
for at least a month between reconnects, and corrects the paste report: physical keyboard typing
works on desktop but Cmd+V does not paste into the remote login window. The user explicitly approved these requirements and parallel implementation through final merge and redeploy. Routine inception/construction/operations checkpoints are covered by that approval; stop only for a consequential new decision outside this scope. Approval recorded 2026-09-20T20:04:41Z.

## Approved requirements

1. **Quiet daily maintenance.** Reuse the existing daemon scheduler and sole browser gate to
   verify and renew each admitted active user's mobile Booking.com session when it has not been
   verified in the previous 24 hours, including users with no monitorable bookings. Reuse recent
   verified foreground/background work instead of duplicating it. Maintenance is read-only,
   makes no model calls, and is bounded to 60 seconds including browser launch. At most two
   verification attempts may each use one negative control and two independent positive probes
   (at most six fixed-URL requests overall, no nested transport retries). This clarifies the original
   two-attempt limit without weakening the existing server authentication contract.
2. **Server-verified lifetime.** An incidental cookie expiry must not expire the entire login.
   Persist cookies only after code-owned positive authentication evidence from the mobile context,
   before any desktop inventory switch. Update the saved freshness metadata atomically; never
   rewrite Booking.com's cookie expiry values. A month between reconnects is a usability target,
   not a guaranteed minimum or a forced monthly logout. Booking.com may revoke a session sooner.
3. **Quiet recovery.** Timeouts, rate limits, server errors, challenges and unrecognized responses
   do not by themselves prove sign-out. Retry with persisted backoff of 15 minutes, 1 hour,
   6 hours and then 24 hours; no restart catch-up burst. Confirmed sign-out or a confirmed need
   for interactive authentication produces one reconnect request per session revision. If recovery
   remains unsuccessful for 48 hours, send one plain-language reconnect request explaining that
   the login could not be verified, without falsely claiming Booking.com signed the user out.
   Successful renewal sends no user notification.
4. **Safe existing-session recovery.** Existing ACTIVE bundles rejected solely by the old local
   aggregate expiry may enter a bounded verification-only path. They become usable only after
   fresh authentication proof. Missing, corrupt, revoked and explicitly reauthentication-required
   bundles remain blocked. Expired individual cookies are not restored. Revision replacement,
   disconnect, user revocation and purge must win over in-flight maintenance; caller isolation
   and encryption remain unchanged.
5. **Desktop and mobile paste.** Explicit Cmd+V/Ctrl+V or a native paste gesture inserts bounded
   plain text exactly once into the selected remote field. Provide a masked native paste field
   and Insert control when clipboard access is unavailable, including mobile Telegram. Preserve
   spaces and supported characters; reject oversized text, unsupported characters and controls rather than truncating or
   generating submit/navigation keys. No automatic form submission.
6. **Transient clipboard handling and verification.** Paste uses the existing authenticated RFB
   keyboard channel; no background clipboard reads, remote-to-local clipboard sync, clipboard
   writes, credential HTTP endpoints, Telegram messages, logging or storage. Clear local text
   immediately after insertion and on teardown; discard asynchronous results after cancellation,
   disconnect, finalization or connection replacement. Test renewal, retry classification,
   legacy migration and concurrency races; test exact-once shortcut/native paste, denied clipboard
   access, Unicode and stale async results. Qualify the packaged noVNC/x11vnc/Chromium stack;
   distinguish automated browser checks from actual Telegram desktop/mobile acceptance.

## Investigation evidence

- `src/booksaver/infrastructure/persistence/cookie_import.py`: imports use earliest expiry of
  any Booking.com cookie as the session-level expiry.
- `src/booksaver/domain/user_session.py`: `refreshed` retains that expiry when no new value is
  supplied; normal coordinator callers omit it.
- `src/booksaver/infrastructure/browser/browser_use_inventory_executor.py`: grouped traversal
  intentionally exports no desktop-mutated cookie snapshot.
- `src/booksaver/infrastructure/browser/browser_use_price_executor.py`: post-run verification
  callback is disabled on the assumption that inventory already refreshed the session.
- `src/booksaver/infrastructure/browser/browser_use_runtime.py`: authentication predicate
  failures need typed classification before being treated as signed-out.
- `src/booksaver/daemon/check_coordinator.py`: existing serialized scheduling and revision-aware
  refresh plumbing can be reused; maintenance must not depend on booking eligibility.
- `src/booksaver/infrastructure/remote_auth/viewer.py`: hidden password input forwards typing
  but there is no local clipboard paste bridge. Desktop shortcuts alone cannot transfer text.
- Intent016's clipboard exclusion must be narrowly amended for explicit one-way user paste.
  No remote clipboard synchronization is proposed.

## Unchanged scope

The 10-minute interactive connect window is separate and unchanged. No passwords or verification
codes are stored for later sign-in, and no autonomous interactive login or reservation mutation
is introduced. No guarantee of a month-long Booking.com session is claimed.

## Measured release limitation

The packaged noVNC/x11vnc/Chromium qualification delivered all 95 printable ASCII characters
exactly but dropped non-ASCII keysyms, including accented characters and emoji, under each tested
x11vnc keymap mode. The initial full-Unicode acceptance target is **not achieved**. The release
delivers the requested verification-code/email/ordinary-password paste without adding a credential
endpoint or remote clipboard retention: unsupported characters are rejected before any text is
inserted, with a clear error. This is a fail-closed compatibility limit, not a passed Unicode test.
The user is informed in progress and final handoff; native Telegram physical input remains separate.

## Release

Released to production on 2026-09-22 as image `continuity-a557487` (merge `8956f4d`). See
`memory-bank/operations/releases/a557487-session-continuity-paste.md`. Live daily renewal and native
Telegram paste are to be confirmed from production behaviour and user feedback.

## Amendment 2026-09-22: seamless mobile paste

7. **Seamless paste (approved 2026-09-23T00:03:03Z).** After native acceptance showed the masked box plus Insert
   to be clunky on mobile, the user asked for the most seamless paste possible. The Paste control
   tries every explicit, user-gesture clipboard source in order: the browser clipboard read, then
   Telegram's Mini App clipboard read (available only where the host permits it), then the masked
   box. Any text that arrives in the box or in the keyboard capture field as one multi-character
   input (a native paste, a suggested one-time code, a keyboard clipboard chip) is sent right away,
   paced for auto-advancing fields, without an Insert tap; characters typed one at a time keep
   Insert. Both local fields advertise `one-time-code` so phone keyboards may suggest codes from
   Messages/Mail/notifications. Requirement 6 is unchanged: no background clipboard reads, no
   Telegram messages carrying codes, no storage, no automatic submission, ASCII-only delivery.

## Amendment 2026-09-23: resumable remote login

8. **Resumable `/connect` (approved 2026-09-23T14:41:37Z).** Leaving the login page to fetch a verification
   code must not end the login. The launch link stays usable by its Telegram owner (fresh signed
   launch data, same user ID) until the attempt ends; each reopening issues a new viewer session
   and revokes the previous one, so exactly one viewer is valid at a time. Leaving the page
   detaches rather than cancels: the remote browser and its Booking.com page stay alive for a
   three-minute grace and resume on return; only the Cancel button, a new `/connect`, the
   timeout or the grace elapsing end it, with a plain Telegram message in the last case. Viewer
   activity slides the deadline forward by the configured session window, never past thirty
   minutes from creation. A reloaded page resumes its existing viewer session before spending
   the link. The single browser gate, credential-blind gateway, replay protection of signed
   launch data and all capture rules are unchanged.
