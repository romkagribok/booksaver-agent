# ADR-019: Fernet (via `cryptography`) for personal-key encryption at rest

- **Status**: accepted
- **Date**: 2026-07-11
- **Bolt**: 009-user-access-and-keys (user-access-and-keys)

## Context

Hybrid billing (FR-3/US-027) lets an invited user of a shared, owner-operated bot supply their
own Anthropic API key via `/setkey` instead of billing the owner's key. That key has to be stored
somewhere the daemon can retrieve it on every price check for that user's bookings — it cannot be
kept only in the Telegram conversation (the message is deleted after intake) or in an env var (env
vars are single-valued and owned by the process, not per-user).

The storage is the existing owner-operated SQLite database (`users.encrypted_key`), on the same
VPS the daemon already runs on. This is materially different from the trust model of every prior
secret in this project (ADR-002: secrets are the *operator's own* credentials, held only in their
*own* env vars, never touching a file at rest). Here, the daemon is now custodian of **other
people's** API keys — invited users who trust the owner to run the bot honestly, but who have no
reason to trust every backup, log export, or disk snapshot of the owner's VPS. Storing these keys
in plaintext would mean a leaked DB file (backup, misconfigured permissions, a copied `.db` for
debugging) directly exposes every invited user's Anthropic account.

Checkpoint 1 (2026-07-11, with the user) approved adding a runtime dependency for this — the
stdlib has no authenticated symmetric encryption suitable for the job.

## Decision

Encrypt personal keys at rest with **Fernet** (the `cryptography` package's high-level symmetric
authenticated-encryption recipe), keyed by a single operator-supplied secret held in the
`BOOKSAVER_SECRET_KEY` environment variable (ADR-002 pattern: secrets live only in env vars, never
in config files or git).

- `infrastructure/crypto/fernet_key_store.py::FernetKeyStore` wraps `cryptography.fernet.Fernet`.
  Constructing it never fails (the env var is read lazily, only inside `encrypt`/`decrypt`) — an
  owner-only/laptop deployment that never sets `BOOKSAVER_SECRET_KEY` and never receives a
  `/setkey` is completely unaffected; the daemon keeps running for every owner-billed user.
- A missing or malformed `BOOKSAVER_SECRET_KEY` raises `SecretKeyError` (a clear, operator-facing
  message) the moment `/setkey` or a personal-key check actually needs it — not at daemon startup,
  and not for users who never opt in.
- Ciphertext is stored as a `BLOB` (`users.encrypted_key`), never plaintext, in the DB, in config,
  or in git.
- The plaintext key is never logged: `monitor/trace.py`'s existing redaction seam (US-022) was
  extended with an unconditional `sk-ant-[A-Za-z0-9_-]{10,}` pattern so a key is redacted from
  traces/snapshots even without a `key=`/`token=` label preceding it.

### Honest security framing

This protects against **exfiltration of the database file or its backups** — the realistic
scenario for "other people's secrets sitting in a file on someone else's server": a stolen backup,
an accidentally-public S3 bucket, a copied `.db` for debugging, a disk image of a decommissioned
VPS.

It does **not** protect against a **fully compromised host**. `BOOKSAVER_SECRET_KEY` lives in the
same process environment the daemon reads `BOOKSAVER_LLM_API_KEY`/`BOOKSAVER_TELEGRAM_BOT_TOKEN`
from — anyone who can read the daemon's environment (root on the VPS, a compromised process, a
misconfigured secrets manager) can decrypt every stored key trivially. This is the same trust
boundary every other secret in this project already accepts (ADR-002); Fernet-at-rest narrows the
*file-exfiltration* attack surface without claiming to solve *host compromise*, which no
software-only measure on a single-secret VPS can. Documented here so this isn't misrepresented as
end-to-end protection for invited users' keys.

## Alternatives considered

- **Plaintext with restrictive file permissions (`chmod 0600`)** — the existing baseline for the
  whole SQLite DB (ADR-001 already sets `0600`/`0700`). Rejected as the *only* protection: file
  permissions don't survive a `cp`/backup/snapshot, which is exactly the scenario multi-tenant key
  storage needs to withstand better than a single-owner DB does.
- **Stdlib-only obfuscation (e.g. `base64`, a hand-rolled XOR)** — rejected outright: this is
  security theater, not encryption, and would be actively misleading to invited users who are
  trusting the owner with their API key.
- **OS keyring (`keyring` package / systemd-creds / OS credential vault)** — rejected for this
  bolt: most keyrings are designed for a single interactive desktop session or require additional
  OS-level setup (`systemd-creds`, `libsecret`, a running D-Bus session) that doesn't fit a
  headless VPS Docker/systemd deployment (US-034) cleanly, and would need a different adapter per
  target OS. Fernet is one small, well-audited dependency that works identically in Docker,
  systemd, and a plain `python3 -m booksaver.cli run` invocation. Worth revisiting if a future
  bolt needs per-key rotation schedules or hardware-backed storage.
- **Per-user encryption keys (derive from each user's Telegram ID + a KDF) instead of one shared
  secret** — rejected as unnecessary complexity: it wouldn't change the host-compromise trust
  boundary (the KDF salt/logic would live in the same compromised process either way) and would
  complicate key rotation (`/admin` has no "rotate `BOOKSAVER_SECRET_KEY`" story; a single secret
  keeps that operationally simple — rotating it means every stored personal key needs
  re-encryption in one pass, a named future-work item, not a blocker for this bolt).
- **No encryption; require users on a shared bot to only ever use owner billing** — rejected: it
  would cut the `/setkey` feature (FR-3/US-027) entirely, which Checkpoint 1 explicitly approved
  as hybrid (owner-billed by default, personal key optional) rather than owner-only.

## Consequences

- New runtime dependency: `cryptography>=42` (pyproject.toml `dependencies`), justified per
  ADR-003's "stdlib genuinely cannot satisfy this" exception, same class of justified addition as
  `playwright` (ADR-007) and `anthropic` (ADR-009).
- Operators running `invite` mode or expecting `/setkey` usage must set `BOOKSAVER_SECRET_KEY`
  (documented in the VPS runbook, `memory-bank/operations/vps-deployment-runbook.md`, as a
  follow-up for the vps-deployment unit) — generated once with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- Rotating `BOOKSAVER_SECRET_KEY` invalidates every already-stored personal key (each user would
  need to `/setkey` again) — acceptable for now; a rotate-in-place migration is named future work,
  not required by any current story.
- `USER_KEY_INVALID` (new `FailureCode`) is the single failure mode this ADR's design surfaces to
  users: a corrupt ciphertext or a missing/rotated `BOOKSAVER_SECRET_KEY` fails only that user's
  checks with an actionable `/setkey`-or-`/deletekey` prompt, never the whole daemon.
