---
id: ADR-063
status: accepted
created: 2026-11-06T02:06:45Z
bolt: 101-claude-data-config-docs
supersedes: ADR-009, ADR-015, ADR-016, ADR-017, ADR-031, ADR-037, ADR-043, ADR-044, ADR-045, ADR-046, ADR-055
amends: ADR-056
---

# ADR-063: TypeSafe's Jev is BookSaver's only model provider

## Context

Since 2026-10-12 every price check ran on Jev; ADR-061 made Jev the reader of reservation totals and
refund terms; ADR-062 removed the disclosure gate that kept the legacy Claude path reachable. The
Claude price methods, the scripted path with its Claude recovery and browser agent, the legacy
inventory source, the model-policy layer, `/setkey` and the Anthropic key were all unused. The owner
wants a single provider with near-zero maintenance.

## Decision

BookSaver uses TypeSafe's Jev as its only model, through `BOOKSAVER_TYPESAFE_API_KEY`. All
Anthropic, Stagehand and Browser Use agent code is removed, together with the Claude spend and
qualification tables, personal Anthropic keys and Claude-era configuration keys (ignored with one
warning). Rollback to Claude is by reverting code, not configuration.

## Consequences

- One provider and one key; tens of thousands of lines and several dependencies fewer.
- A TypeSafe outage stops price checks and new Jev reads; saved facts are kept and the stall message
  reports affected reservations.
- The superseded ADRs remain as history.
