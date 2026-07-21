# VPS Deployment Runbook

**Units:** `005-vps-deployment` (`003-telegram-interface`, bolt 012), plus authenticated
per-user mobile-web operations from intents 012 and 013.

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
- **Networking:** open SSH, outbound HTTPS to `booking.com`, `api.telegram.org`, and your configured
  LLM provider. The Telegram bot itself uses long-polling. When remote authentication is enabled,
  also open inbound TCP 80/443 for Caddy; never open 8080, 5900, or 6080 on the host/firewall.

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
BOOKSAVER_AUTH_DOMAIN=connect.example.com # DNS A/AAAA record must point to this VPS
# BOOKSAVER_SMTP_PASSWORD=...             # optional, only if email alerts are also configured
```

Generate `BOOKSAVER_SECRET_KEY` (a Fernet key used to encrypt both personal LLM keys and each
user's Booking.com session at rest):

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

[browser]
device_profile = "android-chromium"
locale = "en-US"
timezone_id = "America/Indiana/Indianapolis" # choose the operator/user context

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

[telegram_bot]
enabled = true
owner_chat_id = 123456789
poll_timeout_seconds = 30

# Non-owners are always admitted through owner-issued, single-use invites.
# Historical access_mode = "owner" or "invite" values are accepted during
# upgrade but both now normalize to the same fixed invite-only policy.
# check_timeout_seconds = 180

[remote_auth]
enabled = true
public_url = "https://connect.example.com" # must match BOOKSAVER_AUTH_DOMAIN
session_timeout_seconds = 600
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

Before starting, create the DNS A/AAAA record for `BOOKSAVER_AUTH_DOMAIN` and allow TCP 80/443 in
both the VPS provider firewall and the OS firewall. Caddy obtains and renews the TLS certificate.

```bash
docker compose --profile remote-auth up -d --build
docker compose ps                 # should show "healthy" after ~30-60s (start_period)
docker compose logs -f booksaver  # watch the first scheduler tick
curl --fail "https://${BOOKSAVER_AUTH_DOMAIN}/healthz"
```

At this point the bot is running, but price checks intentionally fail with `auth_required` until
each user completes `/connect` as described in §11. Headed `booksaver auth` needs a local display
and is not the phone/VPS path.

## 6. Upgrade procedure

```bash
git pull
docker compose build
docker compose --profile remote-auth up -d # recreate app + TLS sidecar; data persists
docker compose logs -f booksaver  # confirm it comes back up cleanly
```

The `restart: unless-stopped` policy plus `docker compose up -d` handles the kill-and-restart
guarantee from US-034: stop the container (`docker compose stop booksaver` — note a stop issued
mid-check waits for the in-flight browser check to finish, up to `check_timeout_seconds` ≈ 180 s;
`stop_grace_period`/`TimeoutStopSec` are sized for this), start it again
(`docker compose start booksaver`) or just let Docker's restart policy bring it back after a crash
— the scheduler resumes on its own interval and, with the Telegram bot gateway (Unit 001, shipped),
long-polling with `offset`-based acknowledgement means no update is lost or double-delivered across
a restart (Telegram redelivers only un-acknowledged updates).

## 7. Backup of the data volume

`/data` (the named `booksaver-data` volume) contains the SQLite database, the Booking.com session
file, per-check traces, and redacted failure snapshots. **This is guest PII** — booking
confirmation numbers, property names, stay dates, and other users' encrypted
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

## 10. Authenticated mobile-web and VPS-IP validation smoke test

Headed `booksaver auth` needs a display, which a VPS doesn't have. BookSaver's search-journey
checks now require **authenticated mobile web** for every Telegram user. Before a check navigates,
the coordinator resolves exactly the booking owner's encrypted session revision and restores it
into a fresh allowlisted Android Chromium context. Missing, expired, invalid, or rendered-signed-out
state becomes `auth_required`; BookSaver never substitutes public, owner, or another user's rates.
Complete `/connect` from §11 for each admitted user before this smoke test.

By the time you run this smoke test, the Telegram bot gateway (Units 001–004) is also live: use
`/status` from the owner chat instead of/alongside `docker compose exec booksaver booksaver
checks list <booking-id>` for the same daemon-health + last-check view, `/register` to add a
booking straight from chat instead of the `docker compose run --rm booksaver booksaver register
...` one-off shown in §4, and `/checknow` to select one of your active bookings and run the normal
live Booking.com check immediately. The bot stays responsive while that background check runs; if a
scheduled or manual check already owns the single browser gate, retry after its concise busy reply.
Manual checks consume the same per-user daily check and LLM-call limits as scheduled checks. A
detected savings opportunity drives the guided-rebook flow
end-to-end over Telegram (inline-keyboard confirmations, final booking click handed off to your
own device via a deep link) — see `memory-bank/intents/003-telegram-interface/units/`
`004-telegram-rebook-gate/` for that flow's details.

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
   - `success` with a live price and `authenticated mobile web` source provenance → the VPS IP,
     mobile profile, and imported session all work. `Genius observed/present` means Booking.com
     rendered Genius evidence; `Genius not observed` is still valid because not every offer
     participates. Restore your normal `check_interval` if you lowered it.
   - `failure` with code `bot_wall` → Booking.com's interstitial (captcha/"unusual traffic") is
     blocking this IP. Pull the trace for confirmation: `booksaver checks trace <check-id>`.
     Proceed to the fallback ladder below.
   - `failure` with code `step_failed` / `property_not_found` / `no_equivalent_offer` on the first
     attempt → more likely a config/selector issue than an IP block; re-check your booking's
     property name and occupancy (`booksaver bookings set-occupancy`) before assuming a wall.
   - `failure` with code `auth_required` → inspect `/status`, then have that exact user send
     `/connect`. The scheduled notifier also sends a user-scoped reconnect button with a cooldown.

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

## 11. Phone-first `/connect` authentication

This is the normal onboarding and renewal flow. No operator handles JSON cookies and no password,
MFA code, or Booking.com session is sent in Telegram messages.

1. In a **private chat** with the admitted BookSaver bot, send `/connect`.
2. Tap **Open secure Booking.com login**. The button opens a Telegram Mini App at your configured
   HTTPS domain. Do not copy or share this short-lived, single-use link.
3. Sign in on the real Booking.com page shown inside the temporary mobile browser. Google and Apple
   identity-provider top-level navigation is allowed; unrelated destinations and downloads are
   blocked. Complete MFA/passkey prompts if Booking.com requests them.
4. Wait for **Connected** and return to Telegram. BookSaver saves only normalized Booking.com
   cookies after positive rendered account evidence, encrypts them with `BOOKSAVER_SECRET_KEY`, and
   destroys the temporary Chromium/Xvfb/VNC processes and all viewer capabilities.
5. Send `/status`, then `/checknow` for one booking. Confirm the result reports authenticated mobile
   web. `Genius observed` is evidence the page rendered Genius state; `Genius not observed` does not
   mean authentication failed because not every stay/offer has a Genius discount.

The launch capability is bound to the Telegram numeric user ID from signed, fresh Mini App
`initData`; it is exchanged once for an HttpOnly viewer session. Only one check/login can own the
browser lease, so a busy response is normal during another live check. Attempts expire after the
configured timeout and can be cancelled safely. An `auth_required` scheduled result prompts only
the affected user to reconnect and suppresses duplicate prompts for 24 hours.

### Trust boundary

TLS protects the phone-to-VPS connection and BookSaver never receives credentials through its own
form, but the sign-in browser still executes on the VPS. A fully compromised VPS/root account could
instrument that browser or display and observe input. Use this only on a VPS you administer, keep
the OS/Docker patched, restrict SSH, and protect `.env`, `/data`, and backups. The follow-up security
issue linked from Bolt 026 tracks stronger disposable isolation and device-local alternatives.
That follow-up is [GitHub issue #6](https://github.com/roman-marchuk/booksaver-agent/issues/6).

The raw gateway, VNC, and websockify ports must remain private. Verify the deployment exposes only
SSH and Caddy:

```bash
docker compose --profile remote-auth ps
sudo ss -lntp
curl --fail "https://${BOOKSAVER_AUTH_DOMAIN}/healthz"
```

If the button cannot open, check DNS, Caddy certificate logs, `public_url`, and the BotFather Mini
App domain configuration. If Telegram asks for a domain, configure the exact HTTPS host from
`public_url`; never substitute an IP address or HTTP URL.

## 12. Break-glass scoped cookie import

CLI import remains available for recovery when the remote browser cannot complete a provider login.
It is not the normal multi-user flow. Treat an exported cookie file like a password: transfer it only
over SSH, import it for the exact admitted Telegram ID, and delete both plaintext copies immediately.

```bash
scp cookies.json root@YOUR_VPS:/tmp/booksaver-cookies.json
cd /opt/booksaver-agent
docker compose cp /tmp/booksaver-cookies.json booksaver:/tmp/booksaver-cookies.json
docker compose exec booksaver booksaver auth import \
  /tmp/booksaver-cookies.json --telegram-user-id TELEGRAM_USER_ID
docker compose exec booksaver rm /tmp/booksaver-cookies.json
rm /tmp/booksaver-cookies.json
```

Inspect or revoke only that user's redacted session state with:

```bash
docker compose exec booksaver booksaver auth status \
  --telegram-user-id TELEGRAM_USER_ID
docker compose exec booksaver booksaver auth delete \
  --telegram-user-id TELEGRAM_USER_ID
```

Legacy owner state can be migrated explicitly with `booksaver auth migrate-legacy
--telegram-user-id OWNER_TELEGRAM_USER_ID`; it is never used as an implicit Telegram fallback.

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
- ~~**Cookie import**~~ — RESOLVED: the scoped
  `booksaver auth import <file> --telegram-user-id <id>` flow (§12) parses and validates exports,
  encrypts each admitted user's state separately, and fails closed on missing/expired/invalid state.
  Cookie files are deliberately never accepted through Telegram; SSH/SCP is the break-glass intake.
- ~~**Phone authentication**~~ — RESOLVED by Bolt 026: `/connect` launches a Telegram-bound,
  HTTPS-only temporary mobile browser, captures a user-scoped session after positive account
  evidence, and tears the browser down. A real-phone/VPS smoke test remains mandatory before relying
  on it in production.
