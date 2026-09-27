---
intent: 026-jev-price-comparison
phase: inception
status: draft
created: "2026-09-26T16:29:30Z"
updated: "2026-09-26T16:29:30Z"
---

# Implementation handoff

## Start here

The owner wants a complete Jev price method compared with the current Browser Use/Anthropic method
on every eligible user's manual and scheduled price check, with both results/costs visible in Telegram.
This package contains inception only. Do not mistake planned bolts for completed implementation.
Read requirements.md, system-context.md, research.md, experiment-design.md, units.md and the relevant
unit brief, then start bolt 084 using specsmd construction. The user will assign this to another model.

Branch: codex/jev-price-comparison-plan. Base inspected: 78e12cd. Worktree:
/Users/rmarchuk/ProjectCraft/booksaver-worktrees/jev-price-comparison-plan.
A transferable full planning patch is saved at /tmp/booksaver-jev-price-comparison-plan.patch.
Check current status before editing. If this checkout is no longer exclusive, transfer the complete
planning diff to a new owned worktree; never change the shared main checkout. In this environment
/Library/Developer/CommandLineTools/usr/bin/git works despite the default Xcode Git license failure.

## Delivery sequence

1. 084-jev-price-executor: isolated feasibility/reuse spike; prove end-to-end Jev-only evidence path.
2. 085-jev-price-executor: provider, guarded runtime, complete price extraction and exact costs.
3. 086-paired-price-execution: durable pairs, independent arms, isolated effects, budgets and Telegram.
4. 087-price-comparison-qualification: owner comparison report and cohort analysis.
5. 088-price-comparison-qualification: regression/isolated-image qualification and delivery controls.
6. Operations release, explicit paired activation, native Telegram acceptance, multi-day observation.
   Bolt 088 has a pre-release Gate A and live Gate B. Gate A permits operations while its test stage
   and live story criteria remain pending. Complete bolt 088 only after Gate B evidence, never before
   deployment merely to make the status hierarchy green.

All bolts follow domain-model, technical-design, ADR analysis, implementation and test stages.
The user has approved the direction and requested eventual merge/redeployment; the current turn is
restricted to docs. Preserve human review of new artifacts and consequential departures. When the
user hands this to the implementation model, carry forward their authorization instead of asking
again about already authorized routine work. No authority to remove Stagehand or expand inventory.

## Non-negotiable implementation distinctions

- Full independent Jev price flow includes extraction, not just navigation with hidden Claude calls.
- Shared existing inventory is outside the arm boundary and its cost is visible separately.
- Both methods run for each admitted check, not A/B allocation where a user sees only one method.
- They use sequential fresh contexts under one lease, not simultaneous daemons/browser controllers.
- Refactor side effects before pairing: _run_booking and SearchCheckJob._record are not pure.
- Baseline alone affects canonical history/session/savings. Candidate still reports its validated
  experimental result to its user; candidate storage is not an invisible shadow-only trial.
- Record explicit partial outcomes; failures never become no-savings conclusions.
- Forward migration preserves old cost records; rollback does not erase experiment history.

## Proposed files / boundaries

New domain comparison types, application pair orchestration and repository port; a Jev HTTP adapter
under infrastructure/llm; Jev price executor/DOM snapshot helpers under infrastructure/browser;
comparison migrations/repositories under infrastructure/persistence; coordinator integration and
Telegram report formatter/outbox integration. Exact names are chosen in DDD technical design.
Avoid creating a universal provider plugin framework or importing upstream demo server/browser setup.

## Review and operations checklist (planned, not executed)

- Record new ADRs for paired child runs/deadline scope, TypeSafe credentials/egress/disclosure,
  provider costs, and result authority; update affected standards/AGENTS/config docs then.
- Run targeted tests while building; final ruff, mypy, pytest, CLI help, AI-DLC validators and any
  affected browser tests once on the final candidate. Record Linux-only evidence separately.
- Test migrations/foreign keys on cloned state, old rows preserved, disable/restart/rollback, and
  baseline/inventory behavior with paired mode off. Select a rollback image compatible with the new
  schema or qualify disabling the feature on the new image; never blindly boot an incompatible old image.
- Stage the exact image with cloned state and notifications disabled. No independent price probe
  beside the production coordinator. Verify packaged Chromium/cleanup/session and cost behavior.
- Review the final PR head, resolve Cursor threads with tested fixes or evidence, run
  python3 scripts/bugbot_merge_gate.py PR_NUMBER, and require successful current-head Cursor Bugbot.
  Missing/stale/unsuccessful reviews block; no inherited waiver.
- Only after qualification merge and deploy per owner scope; keep restricted backups and Caddy running.
  Verify process/restarts, logs, health, ports, dependencies, SQLite/FKs, and orphan browser processes.
- Provision BOOKSAVER_TYPESAFE_API_KEY securely, confirm pinned model/price/account access/retention,
  set finite caps, publish accurate disclosure and require current invitee acknowledgement. No keys
  through Telegram, tracked config or logs. Current Anthropic consent is not auto-consent to TypeSafe.
- Activate all eligible pairs with a recorded cohort start. Check an owner manual report, disclosed
  invitee manual report and scheduled report natively. Use delivery/restart negatives and kill switch.
- Observe 5–7 days, produce the report, and request the owner's adoption/cleanup decision then.

## Remaining operational inputs

The implementation can start offline now. Live activation needs actual TypeSafe account/key,
explicit finite experiment spending/call/action caps qualified by the spike, the current VPS config,
current provider disclosure and native Telegram recipients with consent. These are not credentials
or deployment facts verified during planning. Missing prerequisites disable/label the candidate,
not silently redirect it to another provider.
