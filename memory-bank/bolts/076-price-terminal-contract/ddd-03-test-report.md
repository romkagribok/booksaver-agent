---
stage: test
bolt: 076-price-terminal-contract
created: 2026-09-14T20:12:23Z
status: complete
---

# Contract verification and ongoing caller diagnosis

The source contract/diagnostic changes pass 2,619 tests (52 existing warnings, 55.89 seconds).
Coverage is 83%: 20,905 statements, 3,471 missed. Ruff and mypy passed; all 16 AI-DLC validator
tests passed, with zero artifact errors and zero status inconsistencies.

Targeted tests prove that the advertised choices equal the eleven existing non-OBSERVED statuses,
invalid terminal values cannot bypass typed observation, successful done still requires the
observation action, and cancellation retains only bounded categories while propagating unchanged.

Actual caller evidence: image B consecutive AIRINN/Park checks passed AIRINN (75.107 seconds) but
Park timed out (179 seconds, 13 model calls, 3 actions, USD0.808159, zero safety violations).
Park alone on the same image later succeeded (87.578 seconds, 5 calls/actions, USD0.188221,
authenticated mobile EUR price). Another consecutive diagnostic replay is in progress. This
pattern is not yet attributed to the terminal contract. No merge or production deployment.

Evidence logs: /tmp/booksaver-076-tests.log, /tmp/booksaver-076-validator.log and
/tmp/booksaver-076-artifacts.log. Candidate caller and exact-image qualification are pending.

## Follow-up observed evidence

The instrumented sequential B run succeeded for AIRINN (72.848 seconds, 3 calls, USD0.112208)
and Park Inn (130.205 seconds, 8 calls, 4 actions, USD0.393550). Park repeated incomplete
submissions after three scrolls, then submitted complete evidence without another browser action.
This weakens the cross-job leak hypothesis and exposes a query/offer completeness instruction
mismatch. The scoped prompt/correction change and its mixed-evidence runtime tests are in progress;
the above 2,619-test result predates that follow-up and is not its final gate.

## Final construction gate

After the query/offer clarification and mixed-evidence regression, the full suite passed:
**2,623 tests**, **52 existing warnings**, **56.19 seconds**. Coverage: **83%**, **20,905
statements**, **3,456 missed**. Ruff/mypy passed, 16 validator tests passed, and artifact/status
validation reported zero errors/inconsistencies. Logs use /tmp/booksaver-076-final-* names.

The existing mapper, observation validator, offer-equivalence rules and budgets are unchanged.
The construction correction is accepted under standing user authorization. Final-head review and
new-image Dev/Staging caller qualification remain Operations gates; neither the two historical
timeouts nor final release verification is erased by construction completion.
