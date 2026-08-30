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
        novnc \
        procps \
        websockify \
        x11vnc \
        xvfb \
    && test -f /usr/share/novnc/core/rfb.js \
    && test -f /usr/share/novnc/core/input/keyboard.js \
    && test -f /usr/share/novnc/core/input/keysym.js \
    && test -f /usr/share/novnc/core/input/keysymdef.js \
    && rm -rf /var/lib/apt/lists/*

# Non-root user the daemon and Chromium run as. Playwright and Stagehand use
# Chromium's container-compatible --no-sandbox mode in this image; the process
# still stays unprivileged, and BookSaver's action/destination guards remain
# the browser authority boundary.
RUN useradd --create-home --shell /usr/sbin/nologin booksaver

WORKDIR /app

ENV ANONYMIZED_TELEMETRY=false \
    BROWSER_USE_CLOUD_SYNC=false \
    BROWSER_USE_VERSION_CHECK=false \
    BROWSER_USE_SETUP_LOGGING=false \
    BROWSER_USE_CALCULATE_COST=false \
    BROWSER_USE_DISABLE_EXTENSIONS=1 \
    BROWSER_USE_CONFIG_DIR=/tmp/booksaver-browser-use-config \
    XDG_CACHE_HOME=/tmp/booksaver-browser-use-cache

# Install Python dependencies first for better layer caching.
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir --requirement requirements.lock \
    && pip install --no-cache-dir --no-deps . \
    && pip check \
    && python -c "from importlib.metadata import version; expected = {'anthropic': '0.125.0', 'browser-use': '0.11.13', 'browser-use-sdk': '3.10.0', 'bubus': '1.5.6', 'cdp-use': '1.4.5', 'playwright': '1.62.0', 'pydantic': '2.13.5', 'pydantic-settings': '2.15.0'}; assert all(version(name) == wanted for name, wanted in expected.items()); from browser_use import ActionResult, Agent, BrowserProfile, BrowserSession, ChatAnthropic, Tools"

# The qualified import above initializes Browser Use's process-wide config/cache paths while the
# image still builds as root. Remove any build-time state and recreate both empty directories for
# the unprivileged daemon; otherwise its first /bookings execution cannot tighten their modes.
RUN rm -rf "$BROWSER_USE_CONFIG_DIR" "$XDG_CACHE_HOME" \
    && install -d -o booksaver -g booksaver -m 0700 \
        "$BROWSER_USE_CONFIG_DIR" "$XDG_CACHE_HOME"

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
