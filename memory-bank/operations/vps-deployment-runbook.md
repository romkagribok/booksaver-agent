# VPS Deployment Runbook

**Unit:** `005-vps-deployment` (`003-telegram-interface`, bolt 012) · **Stories:** US-034 (done),
US-035 core (done — cookie import is a later slice)

Fresh VPS to a running BookSaver bot, in one documented command path, plus the operational
procedures you'll need afterwards.

---

## 1. Provisioning

- **Minimum spec:** 2 GB RAM, 1 vCPU, 10 GB disk. Headless Chromium is the resource-hungry part
  of every check (see `docker-compose.yml`'s `mem_limit` note) — 2 GB is a floor, not a comfort
  margin, if you register more than one or two bookings.
- **Swap:** on a 2 GB box, add 1-2 GB of swap so a transient Chromium memory spike degrades
  performance instead of triggering the OOM killer mid-check:
  ```bash
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```
- **OS:** any recent Debian/Ubuntu LTS is assumed below; adjust package manager commands for other
  distros.
- **Networking:** open only what you need — SSH in, and outbound HTTPS to `booking.com`,
  `api.telegram.org`, and `api.anthropic.com`. BookSaver never needs an inbound port open (the
  Telegram bot uses long-polling, not webhooks).

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"    # log out/in (or `newgrp docker`) to pick this up
docker compose version              # confirm the compose v2 plugin is present
```

(If you'd rather not run Docker at all, skip to §9 for the systemd alternative — everything else
in this runbook still applies, just substitute `journalctl -u booksaver` for `docker compose logs`
and the systemd env file for the `.env` file below.)

## 3. Secrets — env file, never in git

```bash
git clone https://github.com/<you>/booksaver-agent.git
cd booksaver-agent
cp .env.example .env   # if you keep one; otherwise create .env directly (see below)
chmod 600 .env
```

`.env` (same directory as `docker-compose.yml`; **add `.env` to `.gitignore` if it isn't already
covered** — verify with `git check-ignore .env`):

```
BOOKSAVER_TELEGRAM_BOT_TOKEN=123456:AAcalculatedFromBotFather
BOOKSAVER_LLM_API_KEY=sk-ant-...          # owner's Anthropic key
BOOKSAVER_SECRET_KEY=<output of the command below>
# BOOKSAVER_SMTP_PASSWORD=...             # optional, only if email alerts are also configured
```

Generate `BOOKSAVER_SECRET_KEY` (a Fernet key — used to encrypt per-user LLM keys at rest, see
ADR in `memory-bank/intents/003-telegram-interface/requirements.md`):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never commit `.env`, `/data` contents, or `config.toml` with secrets in it. `docker-compose.yml`
fails fast (`${VAR:?set in .env}`) if a required secret is missing, rather than starting silently
misconfigured.

## 4. Config

Create `config.toml` on the host and mount it in, or drop it directly into the named volume before
first start (simplest: start once, then `docker compose exec booksaver sh` — or on the host, run
`booksaver init` locally and copy the file up). A VPS-oriented starting point:

```toml
[schedule]
check_interval = "6h"

[storage]
data_directory = "/data"

[notifications]
# telegram_chat_id = "123456789"   # legacy alert channel; superseded by the
                                    # bot gateway's per-user routing once
                                    # Unit 001/003 land — check CLAUDE.md for
                                    # the current [telegram] config keys.

[extraction]
# model = "claude-sonnet-4-6"

[agent]
# max_steps = 15
# max_llm_calls = 20
# check_timeout_seconds = 180
```

Place it at `/data/config.toml` inside the volume (matches `BOOKSAVER_CONFIG=/data/config.toml`,
set in the `Dockerfile`). One way to get it there without a shell into a running container:

```bash
docker run --rm -v booksaver-agent_booksaver-data:/data -v "$PWD/config.toml":/src/config.toml \
  alpine cp /src/config.toml /data/config.toml
```

Then register your booking (one-off container run against the same volume + env):

```bash
docker compose run --rm booksaver booksaver bookings set-occupancy --help  # sanity check the image
docker compose run --rm booksaver booksaver register --adults 2 ...        # your real booking
```

## 5. First `docker compose up -d`

```bash
docker compose up -d --build
docker compose ps                 # should show "healthy" after ~30-60s (start_period)
docker compose logs -f booksaver  # watch the first scheduler tick
```

At this point the daemon is running unattended and (per §8) checks are logged-out by default —
no headed `booksaver auth` is possible on a display-less VPS, so don't try to run `auth` here; see
§8's fallback ladder if logged-out prices turn out to be unreliable from your VPS's IP.

## 6. Upgrade procedure

```bash
git pull
docker compose build
docker compose up -d              # recreates the container; the named volume (all data) persists
docker compose logs -f booksaver  # confirm it comes back up cleanly
```

The `restart: unless-stopped` policy plus `docker compose up -d` handles the kill-and-restart
guarantee from US-034: stop the container (`docker compose stop booksaver`), start it again
(`docker compose start booksaver`) or just let Docker's restart policy bring it back after a crash
— the scheduler resumes on its own interval and, once the Telegram bot gateway (Unit 001) lands,
long-polling with `offset`-based acknowledgement means no update is lost or double-delivered across
a restart (Telegram redelivers only un-acknowledged updates).

## 7. Backup of the data volume

`/data` (the named `booksaver-data` volume) contains the SQLite database, the Booking.com session
file, per-check traces, and redacted failure snapshots. **This is guest PII** — booking
confirmation numbers, property names, stay dates, and (once Unit 002 lands) other users' encrypted
API keys. Treat backups with the same care as the live deployment: encrypt them at rest, don't
copy them to a shared or third-party host, and delete backups you no longer need.

```bash
docker compose stop booksaver     # quiesce writes for a consistent SQLite snapshot
docker run --rm -v booksaver-agent_booksaver-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/booksaver-data-"$(date -u +%Y%m%dT%H%M%SZ)".tar.gz -C /data .
docker compose start booksaver
```

Restore is the inverse: stop the container, extract the tarball into a fresh/emptied volume, start
the container.

## 8. Log access

```bash
docker compose logs -f booksaver          # follow
docker compose logs --since 1h booksaver  # recent window
docker compose logs --tail 500 booksaver > booksaver.log   # export for sharing/debugging
```

`booksaver checks list <booking-id>` and `booksaver checks trace <check-id>` (run via
`docker compose exec booksaver booksaver checks list ...`) give structured per-check history and
step/agent traces — more useful than raw logs for diagnosing a specific failed check.

## 9. systemd alternative (non-Docker hosts)

See `deploy/booksaver.service` for the unit file and its header comment for the full install
sequence (venv setup, `playwright install --with-deps chromium`, env file, `systemctl enable
--now`). It provides the same `Restart=on-failure` guarantee as `restart: unless-stopped` above;
substitute `journalctl -u booksaver -f` for `docker compose logs -f` throughout this runbook.

## 10. Logged-out checks and the VPS-IP validation smoke test

Headed `booksaver auth` needs a display, which a VPS doesn't have. BookSaver's search-journey
checks therefore default to **logged-out mode**: when no session file exists at
`{data_directory}/session_booking_com.json` (or an existing one is expired/flagged for re-auth),
the scheduled check runs the same search → results → property → room-table journey with no
cookies restored, and reports real public bookable totals. `AUTH_REQUIRED`-class failures cannot
occur in this mode (`SearchJourney`'s failure classifier is gated on session mode — see
`src/booksaver/monitor/search_journey.py` and `src/booksaver/domain/session.py`'s `SessionMode`).
Public prices may miss member/Genius rates; a later slice of US-035 adds an optional cookie-import
path (export cookies from your own browser, load them via CLI/bot) to unlock those.

**Datacenter IPs sometimes get walled by Booking.com's bot detection more aggressively than
residential ones — validate this from your actual VPS before relying on it.** Do this once, right
after step 5:

1. Register a real refundable Booking.com booking you can watch (or use one you already track):
   ```bash
   docker compose run --rm booksaver booksaver register --adults 2 \
     --confirmation-id ... --confirmation-pin ...   # see `booksaver register --help`
   ```
2. Trigger a check. Either wait for the scheduler's next `check_interval` tick (watch
   `docker compose logs -f booksaver`), or lower `check_interval` temporarily to something short
   (e.g. `"5m"`) in `config.toml` and restart the container to force a near-immediate run.
3. Inspect the result:
   ```bash
   docker compose exec booksaver booksaver checks list <booking-id>
   ```
4. **Interpret the outcome:**
   - `success` with a live price → the VPS IP works logged-out. You're done; restore your normal
     `check_interval` if you lowered it for the test.
   - `failure` with code `bot_wall` → Booking.com's interstitial (captcha/"unusual traffic") is
     blocking this IP. Pull the trace for confirmation: `booksaver checks trace <check-id>`.
     Proceed to the fallback ladder below.
   - `failure` with code `step_failed` / `property_not_found` / `no_equivalent_offer` on the first
     attempt → more likely a config/selector issue than an IP block; re-check your booking's
     property name and occupancy (`booksaver bookings set-occupancy`) before assuming a wall.
   - `failure` with code `auth_required` → should not happen in logged-out mode; if you see this,
     it's a bug — file an issue with the trace attached.

**Fallback ladder if the datacenter IP is walled**, in order of effort:

1. **Lower check frequency.** Bot detection is often frequency-sensitive as much as IP-class
   sensitive. Try `check_interval = "12h"` or `"24h"` before reaching for infrastructure changes.
2. **Home server.** Run the exact same container (`docker compose up -d`, same image, same
   `.env`) on a machine behind a residential ISP connection instead of the VPS. This is the
   single highest-leverage fix if step 1 doesn't resolve it, at the cost of needing a
   machine that's on and reachable outbound 24/7 (a Raspberry Pi or old laptop is enough — the
   workload is one headless Chromium tab per check, not continuous).
3. **Residential proxy (last resort).** Route Playwright's traffic through a residential proxy
   provider. This costs money on an ongoing basis and is the most fragile/highest-maintenance
   option, so exhaust 1 and 2 first. Playwright proxy config (would be wired into the
   `InteractiveBrowser` adapter, not this runbook's concern to implement, but noted here for
   planning):
   ```python
   browser = playwright.chromium.launch(
       proxy={
           "server": "http://proxy-host:port",
           "username": "...",
           "password": "...",
       }
   )
   ```
   Evaluate cost, latency (an extra network hop slows an already-multi-step journey and eats into
   the `[agent]` `check_timeout_seconds` cap), and the provider's own ToS before adopting this.

See also `docs/DISCLAIMER.md` (linked from the README) — automated access to Booking.com through
any of the above may violate their Terms of Service; that risk is the operator's, not this
project's, to accept.

---

## Open items / TODOs for whoever picks this up next

- ~~**Healthcheck TODO**~~ — RESOLVED at Wave 1 merge (2026-07-11): the daemon's main thread now
  refreshes `{data_dir}/heartbeat` every ~15 s while all daemon threads (scheduler + Telegram
  poller) are alive (`daemon/lifecycle.py`), and the compose healthcheck is a freshness probe
  against that file (stale > 120 s ⇒ unhealthy ⇒ restart). For the systemd deployment, the same
  file can back an external watchdog (e.g. a cron/timer that `systemctl restart`s on staleness)
  if desired; `Restart=on-failure` already covers crash-exit (the daemon exits nonzero when a
  thread dies).
- **`/status` over Telegram** (US-036) shipped in the same merge — §10's smoke test can use
  `/status` from the owner chat alongside `checks list`.
- **Cookie import** (rest of US-035) is a later slice of this bolt: a CLI file-import command
  (and optionally a Telegram file-upload path with immediate message deletion) for
  member/Genius-rate cookies exported from the user's own browser, with expiry producing a clear
  re-import prompt rather than silent price degradation. Not implemented yet — logged-out mode is
  the only session mode available today.
