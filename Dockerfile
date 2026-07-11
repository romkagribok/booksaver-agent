# BookSaver Agent — VPS deployment image (US-034, bolt 012).
#
# Base: plain python:3.12-slim + `playwright install --with-deps chromium`,
# rather than Microsoft's prebuilt mcr.microsoft.com/playwright/python image.
# Rationale (see memory-bank/operations/vps-deployment-runbook.md): the
# Playwright image tracks a specific Playwright *minor* version tightly coupled
# to its embedded browser build, updates independently of our own release
# cadence, and pulls in extra tooling (multiple browser engines, test runners)
# we never use — BookSaver only ever drives Chromium. Installing Chromium +
# its OS deps explicitly via `--with-deps` keeps the image lean, keeps the
# Python base version choice explicit and current, and matches how we already
# tell contributors to set up locally (`playwright install chromium`).
FROM python:3.12-slim

# Playwright's browser deps installer needs these; kept minimal (--with-deps
# below pulls the rest of the OS-level shared libraries Chromium needs).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Non-root user the daemon runs as. Chromium refuses to run as root without
# --no-sandbox, and we do not want to disable the sandbox, so we install and
# run as an unprivileged user from the start.
RUN useradd --create-home --shell /usr/sbin/nologin booksaver

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Install Chromium + its OS-level dependencies as root (apt access), then hand
# the browser cache to the runtime user.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN playwright install --with-deps chromium \
    && mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" \
    && chown -R booksaver:booksaver "$PLAYWRIGHT_BROWSERS_PATH"

# Persistent data volume: SQLite DB, session file, check traces, failure
# snapshots, config.toml. Never bake secrets or user data into the image.
RUN mkdir -p /data && chown -R booksaver:booksaver /data
VOLUME ["/data"]

ENV BOOKSAVER_CONFIG=/data/config.toml \
    PYTHONUNBUFFERED=1

USER booksaver

# `booksaver run` is foreground-only by design (ADR-005) — no os.fork
# daemonization — which maps directly onto a container's own process model.
# Restarts on crash/OOM are handled by the orchestrator (docker-compose
# `restart: unless-stopped`, or systemd `Restart=on-failure` for the non-Docker
# alternative in deploy/booksaver.service), not by the process itself.
ENTRYPOINT ["booksaver"]
CMD ["run"]
