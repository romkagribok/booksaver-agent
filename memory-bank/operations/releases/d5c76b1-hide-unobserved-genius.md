# Release d5c76b1 — hide unobserved Genius status

## Release identity

- Released at: `2026-07-27T22:32:44Z`
- Environment: owner-operated production VPS (hostname redacted)
- Source: `main` at `d5c76b17de63b7acf8e39a716b602856d1f7d5d9`
- Previous deployed source: `7f4ca4f5be2fe6edf61edb3b993b9f8ff37593bf`
- GitHub delivery: PR #14
- Future authoritative checkout-preview pricing: issue #13
- Release scope: omit ambiguous negative Genius evidence from user-facing check history,
  on-demand results, and savings notifications while preserving authenticated mobile-web source
  provenance and cautious positive evidence.

## Build and staging evidence

- Local quality gate: `963 passed in 13.47s`, Ruff clean, mypy clean across 97 source files,
  AI-DLC artifact/status validators clean, and `git diff --check` clean.
- Exact staged image: `booksaver-agent:staging-d5c76b1`
- Staging image ID:
  `sha256:6f07498d6fe925bc246e8f699aceeb8f1bb9a647b80b07de63563e6b834c2530`
- Staging image size: 624,224,007 bytes.
- Runtime imports, negative/positive Genius rendering, production configuration, required noVNC
  assets, Compose rendering, and Caddy configuration passed before promotion.

## Deployment record

The VPS checkout was fast-forwarded to the merge SHA while preserving existing untracked operator
files. The schema-v11 database was backed up with SQLite's online backup API and verified before
restart. The previous production image was tagged for rollback, the exact staged image was promoted
to `booksaver-agent:latest`, and only the BookSaver service was recreated under the existing
`remote-auth` profile. Caddy remained running.

## Production verification

- Active BookSaver image exactly matches the staged image ID.
- `booksaver`: healthy, zero restarts, and not OOM-killed.
- `booksaver-caddy`: running, zero restarts, and not OOM-killed.
- Release-window application error count: zero.
- Public `/healthz`: HTTP 200 with body `ok`, verified from the VPS and externally.
- TLS certificate valid through `2026-10-18T23:31:46Z`.
- Database integrity: `ok`; schema version 11; foreign-key check empty.
- Daemon heartbeat age: four seconds at verification.
- Production rendering smoke omitted Genius text for `not_observed` provenance and retained
  `Genius evidence visible` for positive evidence.
- Only SSH and TCP 80/443 were publicly listening; raw gateway/VNC ports remained internal.
- Post-startup resources were approximately 412 MiB for BookSaver and 12 MiB for Caddy; about
  6.9 GiB remained available on the root filesystem.

## User acceptance

Run `/checknow` or inspect `/checks` for an authenticated mobile-web result without positive Genius
evidence and confirm no Genius line appears. When Booking.com renders positive Genius evidence,
confirm the result uses the cautious `Genius evidence visible` wording.

## Rollback readiness

- Previous image tag: `booksaver-agent:rollback-7f4ca4f-pre-d5c76b1`
- Schema-v11 online backup: `/data/booksaver.db.pre-d5c76b1`
- Operator backups: `/opt/booksaver-agent/.env.pre-d5c76b1` and
  `/opt/booksaver-agent/config.toml.pre-d5c76b1`

This release has no schema or configuration change. Roll back by retagging the previous image as
`booksaver-agent:latest` and recreating only the BookSaver service with the `remote-auth` profile.
The database backup is recovery evidence and does not need restoration for an ordinary image
rollback.
