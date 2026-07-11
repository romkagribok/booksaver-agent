---
id: US-024
status: complete
implemented: true
---

# US-024 Route commands and multi-step dialogs

**Intent:** `003-telegram-interface`
**Unit:** `001-telegram-bot-gateway`
**Status:** Complete
**Tag:** Phase 3

## Story

**As a** bot user
**I want** commands and step-by-step conversations that guide me
**So that** I can complete multi-question flows (registration, key setup) without memorizing syntax

**Acceptance criteria**

- Given any chat, `/start` and `/help` describe available commands for that user's access level
- Given a multi-step dialog is active in my chat
- When I send a message
- Then it is interpreted as the answer to the current step; invalid answers re-prompt with the expected format
- And `/cancelflow` aborts the dialog from any step with confirmation
- And per-chat dialog state survives a daemon restart or is safely reset with a notice
- Commands and dialogs are registered on a router (units 2–4 plug in without gateway changes)
- The bot layer contains no business rules — it only translates chat to application-service calls

---
