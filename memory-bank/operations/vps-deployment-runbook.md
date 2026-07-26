# VPS Deployment Runbook

This is the operator path from a fresh VPS to a private BookSaver bot, including upgrades,
backups, authentication, and live Booking.com validation.

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
git clone https://github.com/romkagribok/booksaver-agent.git
cd booksaver-agent
cp .env.example .env
chmod 600 .env
```

`.env` is in the same directory as `docker-compose.yml` and is already gitignored. Verify with
`git check-ignore .env` before adding credentials:

```dotenv
BOOKSAVER_TELEGRAM_BOT_TOKEN=123456:AAcalculatedFromBotFather
BOOKSAVER_LLM_API_KEY=sk-ant-...          # optional; scripted/DOM-only if empty
BOOKSAVER_SECRET_KEY=<output of the command below>
BOOKSAVER_AUTH_DOMAIN=connect.example.com # DNS A/AAAA record must point to this VPS
# BOOKSAVER_SMTP_PASSWORD=...             # optional, only if email alerts are also configured
```

Generate `BOOKSAVER_SECRET_KEY` (a Fernet key used to encrypt both personal LLM keys and each
user's Booking.com session at rest):

```bash
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Never commit `.env`, `/data` contents, or `config.toml` with secrets in it. `docker-compose.yml`
fails fast (`${VAR:?set in .env}`) if a required secret is missing, rather than starting silently
misconfigured.

## 4. Config

Copy the tracked non-secret example and edit it locally. Compose mounts this file read-only while
all mutable state stays in the named data volume:

```bash
cp config.toml.example config.toml
chmod 600 config.toml
```

The important VPS settings are:

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
# telegram_chat_id = "123456789" # optional legacy owner alert destination

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

[remote_auth]
enabled = true
public_url = "https://connect.example.com" # must match BOOKSAVER_AUTH_DOMAIN
session_timeout_seconds = 600
```

Validate the one-off CLI path before starting the daemon:

```bash
docker compose run --rm --build booksaver config validate
docker compose run --rm booksaver register --help
```

The normal registration path after startup is `/register` in the private Telegram chat.

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

The `restart: unless-stopped` policy plus `docker compose up -d` handles restarts. Stop the
container with `docker compose stop booksaver`; note that a stop issued
mid-check waits for the in-flight browser check to finish, up to `check_timeout_seconds` ≈ 180 s;
`stop_grace_period`/`TimeoutStopSec` are sized for this. Start it again with
(`docker compose start booksaver`) or just let Docker's restart policy bring it back after a crash
— the scheduler resumes on its own interval and Telegram long-polling resumes from its persisted
update offset.

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

Use `/status` from the owner chat alongside `docker compose exec booksaver booksaver checks list
<booking-id>` for daemon health and the last check, `/register` to add a booking, and `/checknow`
to select one of your active bookings and run the normal
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
   docker compose run --rm booksaver register --help
   ```

   Use the displayed required arguments, or complete `/register` in Telegram.
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

**If the datacenter IP is walled:**

Stop relying on that deployment for monitoring. You may test a lower frequency or move the same
self-hosted stack to a machine on your home connection, but do not use BookSaver to bypass a
challenge or other access control.

See also `docs/DISCLAIMER.md` (linked from the README) — automated access to Booking.com through
any of the above may violate their Terms of Service; that risk is the operator's, not this
project's, to accept.

## 11. Phone-first `/connect` authentication

This is the normal onboarding and renewal flow. No operator handles JSON cookies and no password,
MFA code, or Booking.com session is sent in Telegram messages.

1. In a **private chat** with the admitted BookSaver bot, send `/connect`.
2. Tap **Open secure Booking.com login**. The button opens a Telegram Mini App at your configured
   HTTPS domain. Do not copy or share this short-lived, single-use link.
3. Sign in on the real Booking.com page shown inside the temporary mobile browser using your direct
   Booking.com email and password. Google, Apple, and all other external identity-provider document
   navigation is blocked in main pages, child frames, and popups; ordinary external resources
   required by Booking.com remain available. Complete Booking-owned MFA/passkey prompts if
   Booking.com requests them.
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
That follow-up is [GitHub issue #6](https://github.com/romkagribok/booksaver-agent/issues/6).

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
