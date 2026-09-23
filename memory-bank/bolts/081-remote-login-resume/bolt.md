---
id: 081-remote-login-resume
unit: 003-remote-login-resume
intent: 025-session-continuity-and-paste
type: ddd-construction-bolt
status: complete
stories:
  - 001-resume-connect-after-leaving
created: "2026-09-23T14:41:37Z"
started: "2026-09-23T14:41:37Z"
completed: "2026-09-23T14:41:37Z"
current_stage: null
stages_completed:
  - name: domain-model
    completed: "2026-09-23T14:41:37Z"
    artifact: ddd-01-domain-model.md
  - name: technical-design
    completed: "2026-09-23T14:41:37Z"
    artifact: ddd-02-technical-design.md
  - name: adr-analysis
    completed: "2026-09-23T14:41:37Z"
    artifact: adr-053-resumable-remote-login.md
  - name: implement
    completed: "2026-09-23T14:41:37Z"
    artifact: src/booksaver/application/remote_auth.py
  - name: test
    completed: "2026-09-23T14:41:37Z"
    artifact: ddd-03-test-report.md
requires_bolts:
  - 080-seamless-mobile-paste
enables_bolts: []
requires_units: []
blocks: false
---

# 081-remote-login-resume

Let a /connect login survive the user leaving to fetch a code: owner-reopenable link, detach
grace, sliding expiry and viewer resume. Record actual evidence; device behaviour is user-driven.
