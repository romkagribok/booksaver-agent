---
adr: ADR-051
status: accepted
created: "2026-09-20T20:07:05Z"
bolt: 079-remote-login-paste
---

# ADR-051: Explicit user paste into remote login

## Context

The earlier remote-login clipboard exclusion leaves desktop shortcuts and mobile paste without a
reliable input bridge. The user approved Intent025 requirements 5–6 and this narrow change.

## Decision

Amend the earlier Intent016 clipboard exclusion only for explicit local-to-remote plain-text entry
through the existing RFB keyboard channel. Read the local clipboard once on a trusted user gesture;
use a visible masked native field plus Insert when browser permission or host integration prevents
that read. Preserve literal bounded supported text, release modifiers and never submit automatically.

Retain credential-blind HTTP/gateway/server behavior, no clipboard synchronization or writes,
no storage/logging, and exact connection/generation cancellation of asynchronous work. The local
viewer necessarily holds user-provided text transiently while inserting it, then clears it.

## Consequences

Paste works independently of remote clipboard synchronization and avoids retaining passwords in
remote clipboard state. Keyboard delivery is not a remote acknowledgement: test exact packaged
stack with synthetic values. Native Telegram and physical device behavior remains separately
identified. Permission denial remains usable through native Paste and Insert. No browser security
policy relaxation, new endpoint or autonomous authentication/submission is authorized.

## Qualified release limitation

The installed x11vnc/Chromium stack drops non-ASCII keysyms; bounded flag/locale/compose diagnostics
failed to qualify full Unicode. Release therefore accepts only all-printable-ASCII values and
rejects the entire unsupported value before insertion with a plain message. Full Unicode paste
is explicitly unavailable, not a passed acceptance criterion. This delivers the approved core
verification-code/ASCII email/password paste flow without widening secret transport or retaining
remote clipboard state. Root will disclose the limitation. Remote lock keys are ignored with
x11vnc's `-skip_lockkeys` to prevent CapsLock case corruption while retaining logical client case.
