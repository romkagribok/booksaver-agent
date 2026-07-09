#!/usr/bin/env bash
# BookSaver live test — Westin Hapuna Beach Resort (TEST-001)
#
# Usage:
#   ./scripts/live-test.sh          # full flow: setup → auth → register → run
#   ./scripts/live-test.sh setup    # init + validate only
#   ./scripts/live-test.sh auth     # Booking.com login (interactive browser)
#   ./scripts/live-test.sh register # register test booking (skips if TEST-001 exists)
#   ./scripts/live-test.sh run      # start daemon (first check runs immediately)
#   ./scripts/live-test.sh status   # show checks + savings after a run
#
# Secrets: copy scripts/live-test.env.example → scripts/live-test.env and set
# BOOKSAVER_LLM_API_KEY. Or export it in your shell before running.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Load secrets (optional) ─────────────────────────────────────────────────
if [[ -f "$SCRIPT_DIR/live-test.env" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/live-test.env"
fi

# ── Paths & CLI ───────────────────────────────────────────────────────────────
export BOOKSAVER_HOME="${BOOKSAVER_HOME:-$HOME/.booksaver}"
CONFIG="$BOOKSAVER_HOME/config.toml"
CLI=(python3 -m booksaver.cli --config "$CONFIG")

# ── Your booking (real details from registration) ─────────────────────────────
BOOKING_CONFIRMATION="TEST-001"
BOOKING_PROPERTY="The Westin Hapuna Beach Resort"
BOOKING_PROPERTY_REF="https://www.booking.com/Share-CjZCj9f"
BOOKING_CHECK_IN="2026-08-01"
BOOKING_CHECK_OUT="2026-08-05"
BOOKING_ROOM_TYPE="Guest room, 1 King, Ocean View, Balcony"
BOOKING_AMOUNT="10000.00"
BOOKING_CURRENCY="USD"   # hotel quotes USD; EUR would block savings detection
BOOKING_ADULTS="2"
BOOKING_CHILDREN="0"
BOOKING_ROOMS="1"
BOOKING_REFUND_NOTE="Free cancellation"
BOOKING_REFUND_DEADLINE="2026-07-28"  # before check-in; adjust to match your reservation

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
warn()  { printf '\n\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()   { printf '\n\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

run_cli() {
  "${CLI[@]}" "$@"
}

run_init() {
  # init creates config.toml — must not require an existing --config file
  python3 -m booksaver.cli init --data-dir "$BOOKSAVER_HOME"
}

config_is_valid() {
  python3 -c "import tomllib; tomllib.load(open('${CONFIG}','rb'))" 2>/dev/null
}

repair_config_if_needed() {
  if config_is_valid; then
    return 0
  fi
  warn "Config is invalid TOML — repairing $CONFIG"
  # Earlier script versions appended duplicate [schedule]/[agent] tables.
  if grep -qF "# live-test agent caps" "$CONFIG" 2>/dev/null; then
    sed -i '' '/# live-test agent caps/,$d' "$CONFIG"
  fi
  if ! config_is_valid; then
    die "Config still invalid after repair. Run:
  rm \"$CONFIG\"
  ./scripts/live-test.sh setup"
  fi
  info "Config repaired"
}

apply_test_tuning() {
  info "Applying live-test config tuning (Sonnet agent + relaxed caps)"

  sed -i '' '/# live-test tuning applied/d' "$CONFIG" 2>/dev/null || true
  sed -i '' 's/^check_interval = .*/check_interval = "30m"/' "$CONFIG"

  python3 - "$CONFIG" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

AGENT = {
    "model": '"claude-sonnet-4-6"',
    "max_steps": "40",
    "max_llm_calls": "40",
    "check_timeout_seconds": "420",
}
EXTRACTION_MODEL = '"claude-haiku-4-5"'


def patch_section(src: str, section: str, values: dict[str, str]) -> str:
    pattern = rf"(\[{re.escape(section)}\][^\[]*)"
    match = re.search(pattern, src, re.DOTALL)
    block = match.group(1) if match else f"[{section}]\n"
    for key, val in values.items():
        line = f"{key} = {val}"
        if re.search(rf"^{re.escape(key)} = ", block, re.MULTILINE):
            block = re.sub(rf"^{re.escape(key)} = .*$", line, block, count=1, flags=re.MULTILINE)
        elif re.search(rf"^# {re.escape(key)} = ", block, re.MULTILINE):
            block = re.sub(rf"^# {re.escape(key)} = .*$", line, block, count=1, flags=re.MULTILINE)
        else:
            block = block.rstrip() + f"\n{line}\n"
    if match:
        return src[: match.start(1)] + block + src[match.end(1) :]
    return src.rstrip() + f"\n\n{block}"


text = patch_section(text, "agent", AGENT)
text = patch_section(text, "extraction", {"model": EXTRACTION_MODEL})
if not text.endswith("\n"):
    text += "\n"
text += "# live-test tuning applied\n"
path.write_text(text)
path.chmod(0o600)
PY
}

ensure_config() {
  if [[ ! -f "$CONFIG" ]]; then
    warn "Config missing at $CONFIG — creating it now"
    run_init
  fi
  repair_config_if_needed
  apply_test_tuning
}

require_llm_key() {
  if [[ -z "${BOOKSAVER_LLM_API_KEY:-}" ]]; then
    die "BOOKSAVER_LLM_API_KEY is not set.
  Either:
    export BOOKSAVER_LLM_API_KEY='sk-ant-...'
  Or:
    cp scripts/live-test.env.example scripts/live-test.env
    # edit live-test.env, then re-run"
  fi
}

require_playwright() {
  if ! python3 -c "import playwright" 2>/dev/null; then
    die "Playwright is not installed. Run:
  pip install -e \".[dev]\"
  playwright install chromium"
  fi
}

step_setup() {
  info "BookSaver data directory: $BOOKSAVER_HOME"
  ensure_config

  info "Validating config"
  run_cli config validate

  info "Effective configuration"
  run_cli config show
}

step_auth() {
  ensure_config

  if [[ "${SKIP_AUTH:-}" == "1" ]]; then
    warn "SKIP_AUTH=1 — skipping interactive login"
    return 0
  fi

  if [[ -f "$BOOKSAVER_HOME/session_booking_com.json" ]]; then
    info "Existing session found: $BOOKSAVER_HOME/session_booking_com.json"
    read -r -p "Re-run auth anyway? [y/N] " answer
    if [[ ! "$answer" =~ ^[Yy]$ ]]; then
      info "Using saved session"
      return 0
    fi
  fi

  info "Opening Booking.com login browser (use Terminal.app if the window is not clickable)"
  echo "  1. Log in to Booking.com in the Chromium window"
  echo "  2. Close the browser window when done"
  echo ""
  run_cli auth
}

step_register() {
  ensure_config

  if [[ "${SKIP_REGISTER:-}" == "1" ]]; then
    warn "SKIP_REGISTER=1 — skipping registration"
    return 0
  fi

  if run_cli bookings list 2>/dev/null | grep -qF "$BOOKING_CONFIRMATION"; then
    info "Booking $BOOKING_CONFIRMATION already registered — skipping"
    run_cli bookings list
    return 0
  fi

  info "Registering test booking (inflated baseline to force a savings hit)"
  run_cli register \
    --confirmation "$BOOKING_CONFIRMATION" \
    --property "$BOOKING_PROPERTY" \
    --property-ref "$BOOKING_PROPERTY_REF" \
    --check-in "$BOOKING_CHECK_IN" \
    --check-out "$BOOKING_CHECK_OUT" \
    --room-type "$BOOKING_ROOM_TYPE" \
    --amount "$BOOKING_AMOUNT" \
    --currency "$BOOKING_CURRENCY" \
    --adults "$BOOKING_ADULTS" \
    --children "$BOOKING_CHILDREN" \
    --rooms "$BOOKING_ROOMS" \
    --refund-note "$BOOKING_REFUND_NOTE" \
    --refund-deadline "$BOOKING_REFUND_DEADLINE"
}

booking_id_for_confirmation() {
  local db="$BOOKSAVER_HOME/booksaver.db"
  if [[ ! -f "$db" ]]; then
    return 0
  fi
  sqlite3 "$db" \
    "SELECT booking_id FROM bookings WHERE confirmation_id='$BOOKING_CONFIRMATION' LIMIT 1;" \
    2>/dev/null || true
}

step_status() {
  ensure_config

  local booking_id
  booking_id="$(booking_id_for_confirmation || true)"

  info "Registered bookings"
  run_cli bookings list || true

  if [[ -z "${booking_id:-}" ]]; then
    warn "No booking id found for $BOOKING_CONFIRMATION — run register first"
    return 0
  fi

  info "Recent checks for booking $booking_id"
  run_cli checks list "$booking_id" || true

  info "Savings opportunities"
  run_cli savings list || true

  echo ""
  echo "Debug a specific check:"
  echo "  python3 -m booksaver.cli --config \"$CONFIG\" checks trace <CHECK_ID>"
}

step_run() {
  ensure_config
  require_llm_key

  info "Starting daemon — first price check runs immediately"
  echo ""
  echo "  Wait up to ~5 minutes. Do NOT press Ctrl-C until you see:"
  echo "    Job 'booking_com_check' completed (tick 1)"
  echo ""
  echo "  In another terminal, inspect progress:"
  echo "    ./scripts/live-test.sh status"
  echo ""
  echo "  Stop the daemon after tick 1 with Ctrl-C (safe once the job completed)."
  echo ""

  run_cli run
}

step_all() {
  require_playwright
  require_llm_key
  step_setup
  step_auth
  step_register
  step_run
}

# ── Main ──────────────────────────────────────────────────────────────────────
ACTION="${1:-all}"

case "$ACTION" in
  setup)    step_setup ;;
  auth)     require_playwright; step_auth ;;
  register) step_register ;;
  run)      require_playwright; step_run ;;
  status)   step_status ;;
  all)      step_all ;;
  *)
    die "Unknown action: $ACTION

Usage: $0 [setup|auth|register|run|status|all]"
    ;;
esac
