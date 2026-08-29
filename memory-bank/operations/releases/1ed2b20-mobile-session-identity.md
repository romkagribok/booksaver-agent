# Release 1ed2b20 — mobile session identity

## Release identity

- Released at: `2026-08-29T21:26:00Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source and runtime source: `main` at `1ed2b20562fb3276ed654a4a3d12071a1e065841`
- Previous deployed runtime source: `88eeac7914fd9c0fe1d8923383f2ff428ec114d4`
- GitHub delivery: PR #35. Cursor Bugbot found that the initial mobile-browser repair left
  computer-use coordinates at the former desktop viewport. The final head aligned screenshots,
  tools, scrolling, hit-testing, and guards with the launched viewport; the current-head Bugbot
  merge gate passed at `f8f3d939fe624819d320810aca4947f3b1a10716` before merge.
- Release scope: preserve the configured mobile browser identity when a local Stagehand browser
  consumes an authenticated session, and classify browser transport failures before semantic or
  computer-use work.

## AI-DLC construction evidence

- Corrective bolt `059-agentic-inventory-executor` and US-159 completed through the DDD stages and
  mandatory completion cascade under intent 023.
- Browser identity is now a compatibility invariant: both price and inventory Stagehand runtimes
  use the configured Playwright-version user agent, viewport, device scale, touch, and locale.
- The runtime owns one CSS viewport used by screenshots, computer-use tool declarations, scroll
  targeting, coordinate proposals, hit-testing, and action guards.
- Top-level redirect loops and other navigation failures become closed, content-free categories
  before Stagehand extraction, screenshots, or Anthropic computer use. Inventory redirect loops
  map to signed-out; other transport failures fail closed as provider failures.
- Local release gate: 1,805 tests passed with 55 existing deprecation warnings; Ruff and strict
  mypy passed across 127 source files; artifact validation and status integrity reported zero
  issues across 59 bolts and 23 intents; `git diff --check` passed.

## Build and staging evidence

- Exact production image ID:
  `sha256:636ba4c962f1f23c072e6dfcfbd2d32025e395bf524443f1aa11a16479585572`.
- Image size: 635,746,404 bytes; OCI revision label exactly matches merge SHA `1ed2b20`.
- Stagehand 4.0.1, Anthropic SDK 1.2.0, Playwright 1.62.0, and Chromium 151.0.7922.34 are installed
  in the exact image.
- Before merge, an isolated VPS candidate using the production encrypted session reached the
  protected `/mytrips.html` route with the configured Android mobile identity and zero popups.
- After deployment, the exact merged image repeated the isolated authenticated smoke against the
  current encrypted session and reached `/mytrips.html` with zero popups. It made no model call,
  persisted no browser evidence, and did not start a second coordinator.

## Deployment record

The previous production image was tagged
`booksaver-agent:rollback-88eeac7-20260829T212328Z`. A quiesced data-volume archive, `config.toml`,
and `.env` were preserved in `/opt/booksaver-backups/20260829T212328Z-pre-` before promotion with
mode 0600. The archive checksum, SQLite integrity check, and foreign-key check passed against an
isolated extracted copy.

The first promotion attempt stopped at its pre-deployment SQLite probe because that probe used an
incompatible read-only container context. The deployment trap automatically restored the previous
image and verified it healthy. The archive was then validated in an isolated root-owned temporary
context, and promotion resumed without restoring or modifying database data.

The VPS checkout was fast-forwarded to the merge SHA while preserving untracked operator files.
Only the BookSaver service was recreated; Caddy retained its container identity and four-week
uptime.

## Production verification

- Active checkout, OCI revision label, `latest` tag, and running BookSaver image resolve to merge
  `1ed2b20` and image `636ba4c`.
- BookSaver is healthy with zero restarts and no OOM kill. A delayed stability poll remained clean;
  idle memory was 39.27 MiB of the 2 GiB limit and no Chromium process remained.
- Heartbeat age remained below 11 seconds. Release-window and delayed logs contain no traceback,
  critical, unhandled, exception, or error entries.
- Live SQLite remains at schema 17 with integrity `ok`, zero foreign-key violations, and preserved
  counts: three users, four account reservations, two monitoring bookings, 233 synchronization
  runs, and 13 redacted agentic inventory execution records.
- Production config validates with `agentic` inventory routing, `owner_canary` price routing,
  Anthropic disclosure v1, the existing USD 1 job and USD 10 UTC-day limits, and no budget change.
- Telegram Bot API `getMe` succeeded. Public `/healthz` returned 200; Booking.com returned 202; the
  Anthropic endpoint completed TLS/HTTP reachability with its expected unauthenticated 404.
- BookSaver continues to expose only ports 8080/6080 inside Compose. Caddy alone retains public
  ports 80/443 and was not recreated.

## User acceptance

The owner should now run `/bookings` in Telegram. That exercises the full authenticated Stagehand
inventory traversal and typed extraction path; the isolated automated smoke proved only session
compatibility and protected-route navigation, not Booking.com's current page perception.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-88eeac7-20260829T212328Z`.
- Data/config/env backup: `/opt/booksaver-backups/20260829T212328Z-pre-`.
- The backup archive passed SHA-256, SQLite quick-check, and foreign-key validation.

This release does not change the database schema or routing configuration. Image rollback requires
retagging the saved rollback image as `booksaver-agent:latest` and recreating only BookSaver.
Restoring the database archive would discard post-deployment state and requires separate explicit
data-loss approval.
