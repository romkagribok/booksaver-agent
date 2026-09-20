---
stage: test
bolt: 079-remote-login-paste
created: "2026-09-20T20:11:26Z"
status: complete
---

# Explicit paste verification

Initial viewer/browser and gateway tests passed **78 tests in 40.60 seconds** against mocked
RFB. That initial result did not qualify Unicode delivery; the actual-stack failure and final
qualified release scope are recorded below. Final integrated quality gate/review/release remain pending.

The browser tests verify Cmd/Ctrl+V interception, one read/send, initial Unicode keysym encoding and
spaces, controls/newlines/unpaired-surrogate/oversize rejection, missing/denied Clipboard API,
masked field requiring Insert, buffer clearing, delayed clipboard resolution after cancellation,
finalization, pagehide or connection replacement, and mid-chunk disconnect. Pending operations
block remote pointer/key input and Next/Enter so text cannot move between fields or submit while
being inserted. Synthetic untrusted paste events do nothing.

A browser-generated trusted paste event test seeds only synthetic text into Chromium's clipboard,
then uses an automated native shortcut in the fallback field. It checks raw newline rejection
before password-input newline normalization and buffer-only behavior before Insert. This is not
a physical OS or Telegram test. The RFB module is mocked in these local tests.

## Packaged-stack qualification plan

Operator-only `/tmp/remote_paste_stack_probe.py` is prepared and compiles, but has not yet run.
Run it in an isolated candidate image with no external network, no /data mount, no PYTHONPATH,
and the script mounted read-only. It requires the installed viewer and packaged noVNC/x11vnc,
starts an ephemeral Xvfb plus remote headed Chromium dummy form and a local headless Chromium
viewer. Synthetic text only; no real login or secrets. API authorization/state are test stubs;
the input implementation and RFB stack are real.

Assert exact remote field value for Ctrl+V, Cmd+V and native masked fallback, preserved remote
focus, a normal following key (released modifiers), no other-field mutation or form submission,
and cleared local buffer. Print counts only; stop child processes and delete ephemeral files.
The probe does not qualify real Telegram or physical device clipboard permissions. Native device
acceptance remains separately identified rather than inferred from automation.

## Initial packaged Dev qualification failure

The viewer-only isolated image `booksaver-agent:paste-dev`, based on the qualified production
image, failed the first exact Unicode field-value assertion. Synthetic diagnostics established
correct remote focus and modifier release; ASCII/spaces arrive, but é, 例 and 🔐 become empty X11
key symbols in Chromium although noVNC sends their correct keysyms. Repeating after mapping
settles and testing x11vnc xkb/noxkb/modtweak/nomodtweak/add_keysyms/xkbcompat combinations did
not fix this. Explicit UTF-8 locale and GTK IM settings did not qualify Linux compose; it emitted
literal hexadecimal text. Diagnostic-only remote clipboard transfer also did not qualify.
None of these diagnostic alternatives changed product source or production.

A separate unchanged-image ASCII-only probe passed **12 checks, zero failures**: both automated
Ctrl+V and Meta+V deliver all 95 printable ASCII characters exactly, a following ordinary key
works, and native masked fallback preserves text until Insert, clears it afterward and does not
submit or modify another field. This is synthetic packaged-stack evidence, not physical Telegram
acceptance. Full Unicode acceptance remains blocked; any narrowed supported-character contract
requires an explicit design/requirements disposition before release. The product must not send
partially altered credentials.

## Final scoped clipboard implementation gate

After fail-closed character preflight, lock-key protection and key-release continuity changes,
**101 targeted tests passed in 43.80 seconds** across viewer browser, gateway and remote runner
suites. Scoped Ruff passed; mypy passed both changed source modules. This includes every printable
ASCII character, unsupported Latin/CJK/astral/combining characters rejected before any send,
trusted native fallback validation, modifier release during pending reads and both device launch
configurations retaining `-skip_lockkeys`.

The rebuilt viewer/runner-only installed image passed **24 synthetic packaged-stack checks**:
CapsLock toggled before Ctrl+V/Meta+V, all 95 printable ASCII values preserved exactly, ordinary
`Aa0!?` typing afterward, four Unicode inputs rejected without remote mutation/submission,
ordinary typing after each rejection, and native masked fallback requiring Insert then clearing.
This qualifies the accepted core ASCII code/email/password paste flow. Full Unicode remains
unavailable and is rejected, not silently corrupted or represented as implemented.

Final reusable probe: `/tmp/booksaver-continuity-release/paste_stage_probe.py`. It reads the
installed production runner's x11vnc argv from its AST, overrides only fixture display/port, and
requires exactly one `-skip_lockkeys`; it does not silently substitute different server flags.
The final full-image staging replay must use this probe with `--init`, no external network and
no production data mount. Viewer-only Dev qualification does not replace that Operations gate
or native Telegram/physical device acceptance. Product source is frozen pending integration.

## 2026-09-20T20:24:46Z — integrated construction gate

Final combined source passed **2,949 tests**, with one Linux-only cleanup test skipped on macOS,
52 existing warnings, in 68.54 seconds. Ruff and mypy (125 modules) passed. All 16 AI-DLC validator
tests passed; artifact/status validation had zero errors/inconsistencies. The prior full run found
three stale safety-test host fixtures; adding the new optional verified-session field retained all
dialog/tab/navigation rejection assertions, and the 73-test traversal selection passed before the
final full run. Exact combined-image Dev/Staging, current-head Bugbot and production remain separate
Operations gates. Unicode paste is an explicit unsupported-character rejection, not full-Unicode
acceptance; no physical Telegram test is claimed. User approved scoped completion through release.
