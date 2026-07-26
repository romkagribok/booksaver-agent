# BookSaver repository guidance

## Product and current state

BookSaver Agent is a self-hosted Python daemon/CLI and private Telegram bot. It monitors refundable
Booking.com hotel reservations, detects cheaper equivalent offers through scripted browser
automation with bounded LLM assistance, and guides rebooking with mandatory human confirmation.

The implemented scope is 92 in-scope stories across intents 001-013, 26 completed bolts, schema
v10, 26 ADRs, and 870 tests. Two assigned extensibility stories remain explicitly post-MVP. See
`memory-bank/story-index.md` for status and `memory-bank/standards/decision-index.md` for decisions.

## Commands

```bash
pip install -e ".[dev]"
playwright install chromium
python3 -m ruff check src tests
python3 -m mypy src
python3 -m pytest
python3 -m booksaver.cli --help
```

Python 3.11+ is required. Runtime dependencies are Playwright, Anthropic, and cryptography.

## Non-negotiable boundaries

- Booking.com hotels only; registered and candidate offers must be refundable.
- Equivalence requires the same property, stay dates, room type, and occupancy.
- Compare currency-aligned, all-in bookable totals; fail closed on ambiguity.
- Never autonomously cancel, reserve, purchase, pay, or submit a final booking action.
- The final rebook action stays on the user's device after explicit confirmation.
- Self-hosted owner/invite access only; no public bot or BookSaver-operated backend.
- Keep config, SQLite, cookies, encrypted keys, traces, and snapshots locally controlled.
- Secrets come only from `BOOKSAVER_LLM_API_KEY`, `BOOKSAVER_SMTP_PASSWORD`,
  `BOOKSAVER_TELEGRAM_BOT_TOKEN`, and `BOOKSAVER_SECRET_KEY`.
- Preserve per-user booking, session, alert, usage, and admin-visibility boundaries.
- Browser-agent actions remain bounded and adapter-guarded; provider output is untrusted.

## Architecture

Keep the single-process, stdlib-first architecture and explicit domain types. Browser automation,
LLM interpretation, persistence, savings evaluation, notifications, access control, and rebook
confirmation must stay behind separate module boundaries. Binding architecture and technology
constraints are in:

- `memory-bank/standards/system-architecture.md`
- `memory-bank/standards/tech-stack.md`
- `memory-bank/standards/coding-standards.md`
- `memory-bank/standards/decision-index.md`

## specs.md AI-DLC

The project uses specs.md AI-DLC for accepted requirements and consequential changes:

- `.specsmd/aidlc/` is the installed framework source.
- `.specsmd/aidlc/memory-bank.yaml` is the artifact schema.
- `memory-bank/` is the project source of truth.
- `.agents/skills/`, `.claude/`, and `.cursor/` are tool discovery adapters, not authority.

Start methodology work with the specsmd master agent. Use inception for requirements/design,
construction for approved bolts, and operations for build/deploy/verification. Preserve human
checkpoints and keep `memory-bank/story-index.md` consistent with story changes.

## Working agreement

- Inspect narrowly and preserve unrelated user work.
- Discuss consequential design and security tradeoffs before implementation.
- Use parallel execution workers for independent, bounded work when the environment supports the
  repository's configured worker model; the main agent owns integration and verification.
- Run targeted checks while editing and the full relevant quality gate before handoff.
- After starting or deploying a service, verify process state, logs, health, ports, and dependencies.
- Do not commit, push, merge, deploy, or change external state without the user's explicit approval.
- Use Conventional Commits with a concise single-line subject when approval is given.
