---
version: continuity-a557487
created: "2026-09-20T20:31:21Z"
updated: "2026-09-22T01:42:44Z"
status: complete
---

# Deployment history

## Candidate continuity-53d021c (superseded)

The exact installed image passed network-disabled Dev: SQLite/FKs, Chromium and clean SIGTERM
in 2.7 seconds. Linux supervisor tests confirmed cleanup for hung startup (1 process, 5,020 ms),
detached child (2 processes, 5,021 ms), and hung Chromium close (7 processes, 5,040 ms).
Packaged noVNC/x11vnc/Chromium passed 24 synthetic checks. Read-only production-volume Staging
cloned SQLite and the encrypted vault, then made only the cloned legacy ACTIVE aggregate locally
expired. Normal maintenance passed 32 assertions: fresh Booking.com proof recovered it, stored
policy version 1, no aggregate expiry and a daily due time, and a new coordinator honored NOT_DUE
after restart. All 659 other-caller rows, other callers' vault files and original production
database/vault digests stayed unchanged. Evidence: `build-53d021c.log`, `dev-53d021c.log`,
`stage-53d021c.log` in `/opt/booksaver-releases/continuity-20260920/`. Superseded by a Bugbot
paste-retry correction (2632af8) and then by review corrections (a557487); never promoted.

## Candidate continuity-2632af8 (superseded)

Dev on the exact image passed installed-source/dependency verification, `pip check`, the isolated
smoke (2.74 s), all three Linux supervisor cleanup cases and **27 packaged paste checks**
(`dev-2632af8.log`). Current-head Bugbot passed. Superseded before promotion by the pre-release
review corrections recorded in Bolt 078's test report; never promoted.

## Final candidate continuity-a557487

Image `sha256:cb35711dc21eadba038f4f6fbcb82ef4b79bb4fffd76ce5d27389e93212c2700`, source
`a557487c0976725a651a1cf3f858a46b18f36a33`. Current-head Cursor Bugbot **passed** for a557487.

**Dev (2026-09-22, `dev-a557487.log`)**: 125 installed modules and eight dependency pins matched,
`pip check` clean; isolated network-disabled smoke passed (SQLite/FKs, Chromium, clean SIGTERM,
2.69 s); Linux supervisor cleanup confirmed for hung startup (1 process, 5,018 ms), detached child
(2 processes, 5,021 ms) and hung Chromium close (7 processes, 5,040 ms); packaged noVNC/x11vnc/
Chromium paste probe passed **27 checks, 0 failed** with synthetic input only. Physical Telegram
acceptance is not claimed.

**Staging, first attempt (2026-09-22T00:10:46Z, `stage-a557487.log`)**: the read-only
production-clone replay stopped at its fifteenth assertion with **14 passed / 1 failed** because
the live verification returned RETRY_LATER, and production was restored healthy under the trap in
43 seconds. Content-free diagnostics inside the same staging container established the cause:
cookies decoded (16 of 16 unexpired), Chromium launched in 0.7 s, and Booking.com's CloudFront edge
answered both the anonymous negative control and the cookie-bearing positive probe with the
known **202 text/html, empty-body, no-redirect edge-pending** tuple. The verifier correctly
classifies that as not proof (fail closed) rather than as sign-out. Production foreground checks
for the same caller succeeded at 2026-09-21T20:38Z on the current image, so the saved session is
valid; the edge state is transient. Staging will be replayed once the anonymous control again
returns the normal sign-out redirect. Diagnostics emitted only outcome names, counts, status
codes, media types and hostnames; no body, header values, cookies or account data.

**Staging disposition (2026-09-22T01:42:44Z)**: the user directed release without a repeat live replay to let
the VPS IP cool off; the earlier 32-check replay of the identical verification code on
`continuity-53d021c` plus the final-image Dev evidence are the accepted staging proof. Production
behaviour of daily maintenance is to be observed from persisted session metadata and user feedback.

## Production promotion

PR #55 merged at **2026-09-22T01:40:43Z** as `8956f4d5a01eb025c38b94b0059c282f49e325bc` after the
executable Bugbot gate passed for head a557487 (one successful check, one resolved Cursor thread).
`promote.sh 8956f4d…` stopped only BookSaver, wrote backup
`/opt/booksaver-backups/continuity-a557487-20260922` (directory 0700; `data.tar.gz`, `config.toml`,
`environment.env`, `SHA256SUMS` all 0600; archive SHA-256
`1e89dbd00f9e01feeb4ac424744b76465dc65e92e30b9da8e663a8e256db6e7b`, tar listing and checksum
verified), passed pre-promotion SQLite integrity/FK checks, fast-forwarded the VPS checkout to the
merge, tagged the prior image `booksaver-agent:rollback-pre-continuity-a557487`
(`sha256:cddc642f…`), retagged `latest` to `sha256:cb35711d…` and recreated only BookSaver.
Daemon started **2026-09-22T01:41:23Z**; the script reported healthy at **2026-09-22T01:41:34Z**
with internal health, SQLite integrity/FKs, public health and an unchanged Caddy container.
Log: `promotion-a557487.log`. Rollback: retag `latest` to the rollback image and recreate; no
data restore is implied by an image rollback.
