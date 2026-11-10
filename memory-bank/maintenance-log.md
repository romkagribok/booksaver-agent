
## 2026-07-26T18:12:11.271Z - Status Sync

**Triggered by**: status-integrity script

| Artifact | Old Status | New Status | Reason |
|----------|------------|------------|--------|
| intents/014-remote-auth-display-reliability/units/001-remote-auth-display-reliability/unit-brief.md | ready | in-progress | Unit has 1 bolts (0/1 complete) |
| intents/014-remote-auth-display-reliability/requirements.md | complete | units-defined | Intent has 1 units (0/1 complete) |

---

## 2026-07-26T19:46:14.570Z - Status Sync

**Triggered by**: status-integrity script

| Artifact | Old Status | New Status | Reason |
|----------|------------|------------|--------|
| intents/015-authentication-boundary-hardening/units/001-complete-user-purge/unit-brief.md | stories-defined | in-progress | Unit has 1 bolts (0/1 complete) |
| intents/015-authentication-boundary-hardening/units/002-direct-booking-auth-only/unit-brief.md | stories-defined | in-progress | Unit has 1 bolts (0/1 complete) |

---

## 2026-07-26T21:23:02.084Z - Status Sync

**Triggered by**: status-integrity script

| Artifact | Old Status | New Status | Reason |
|----------|------------|------------|--------|
| intents/015-authentication-boundary-hardening/requirements.md | units-defined | construction | Intent has 2 units (0/2 complete) |

---

## 2026-10-10T01:49:50Z - AI-DLC process reconciliation (intent 026)

**Triggered by**: owner request to confirm that recent changes followed AI-DLC

Findings and corrections for PRs #73, #75 and #76:

| Gap | Correction |
|-----|------------|
| specsmd agents were not invoked; bolt-type stage checkpoints were skipped for bolts 084 to 086 | Recorded in each bolt's test report and construction log; owner reviewed on 2026-10-07 and chose to proceed |
| Bolts 084 to 086 left `in-progress` after live acceptance; completion script never run | Live evidence and per-criterion disposition added; completed with `bolt-complete.cjs` |
| No construction logs | Created for units 001 to 004, with reconstructed entries labelled as such |
| PR #75 (question wording) and PR #76 (diagnostics) shipped outside any story or bolt | Traced by US-216 background and US-218 (retroactive) |
| No release records for the 2026-10-01 and 2026-10-04 promotions; `.env` variable rename unrecorded | `operations/releases/18f367e-*.md` and `ac72f12-*.md` added from the kit logs |
| Bolts 087 and 088 never started | 087 completed with the decision report; 088 started, open on the kill-switch criterion |
| Unmet acceptance criteria | Listed as descoped in the requirements amendment, not marked delivered |
| Cursor Bugbot ran on none of the four PRs (usage limit; standing waiver applied) | Recorded; no automated review exists for this code. One independent agent review ran before PR #73 |

Operational finding recorded here because no story covers it: on 2026-10-03T18:04Z a timed-out run
of the existing Browser Use price method left its Chromium running for 9.3 hours (about 800 MB,
holding an invitee's signed-in session). Recreating the container cleared it on 2026-10-04. The
teardown defect is not fixed.

---

## 2026-11-10T00:56:42Z - AI-DLC process reconciliation (intents 030 to 034)

**Triggered by**: owner request on 2026-11-09 to report how well AI-DLC was followed

Findings and corrections for bolts 100 to 105 (PRs #102, #103 and #105 to #107):

| Gap | Correction |
|-----|------------|
| specs.md agents (master, construction, operations) not invoked since 2026-11-03; stage documents, construction logs and release records were written directly | Recorded in the construction logs of units 032-001, 033-001 and 034-001 and in bolts 103 to 105. This close-out ran through the master agent, the operations agent's verify step and the construction agent's completion procedure |
| Bolt-type stage stops skipped; one owner go-ahead per piece of work covered commit, merge and deploy | Covered retroactively by the owner's standing waiver of 2026-11-09 ("human checkpoints may be skipped as they have been, I am under control"); recorded in the bolts and construction logs |
| Bolts 100, 101, 103, 104 and 105 left `in-progress` after deploy; release records left at `deployed-awaiting-readback` | Read-only production read-back on 2026-11-10T00:45Z to 00:49Z added to the four release records (now `deployed-verified`) and the bolts' test reports. Bolts 100, 103, 104 and 105 completed with `bolt-complete.cjs` at 2026-11-10T00:55:34Z to 00:55:35Z. Bolt 101 stays open: US-253's docs criterion is not met (`.env.example` still names `BOOKSAVER_LLM_API_KEY`, behind a local deny rule, for the owner to remove). ADR-019, still `accepted` for personal Anthropic keys, was marked amended by ADR-063 |
| Issues #79 and #3, required closed by US-253, were still open | Closed with a summary at 2026-11-10T00:54:03Z (#79, completed) and 00:54:04Z (#3, not planned) |
| Release records for `noavail-39a666b`, `jevroom-86279b0` and `jevfacts-21694ab` written at deploy time but left uncommitted in a temporary worktree | Carried into this close-out and committed with it; not backdated |
| `story-index.md` out of step: US-249 to US-253 and US-255 to US-257 still `Planned`; intent 031's construction log showed bolt 102 `in-progress` and US-254's criteria unticked although complete | Index updated to the story files; bolt 102's row corrected; US-254's four criteria ticked against the test, replay and production read-back |
| PR #105 merged while `scripts/codex_merge_gate.py 105` reported an unresolved Codex thread, because a pipe hid the gate's exit status | The finding had already been fixed and re-reviewed clean; the thread was resolved after the merge. PRs #106 and #107 ran the gate on its own (exit 0) before merging |
| Production read-back limits | Daemon logs from 2026-11-06 to 2026-11-10T00:41Z were lost when another session recreated the container, so "no errors" rests on database outcomes; Jev confidence values are not stored in production; US-252's warning and US-257's personal-data removal are evidenced by tests only; user 3's scheduled sync at 2026-11-09T20:23:32Z ended `incomplete` on a different inventory path |

Operational finding recorded here because no story covers it: on PRs #106 and #107 Codex found that
personal reservation details (guest name, confirmation number, PIN, email, label values) could reach
TypeSafe. The pre-fix code had already been run against real reservation pages with live Jev during
staging on 2026-11-08, so some personal details probably left the host then. This is inferred from the
session timeline; the request payloads were not inspected. Both findings were fixed before merge.

Owner's rule going forward (2026-11-09): every change, however small, has its documents present before
the code (intent, requirements, unit, story, bolt with stage artifacts, construction log; story index in
step); every build, deploy and verification goes through the specs.md operations agent, with a release
record committed and merged to `main`; everything is closed once live and observed (release read-back
and final status, `bolt-complete.cjs`, story, unit, intent and index statuses, worktree removed); human
checkpoints may be skipped under the standing waiver, while the Codex merge gate still applies.

---
