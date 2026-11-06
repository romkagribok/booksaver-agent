---
unit: 003-delete-claude-code
bolt: 100-delete-claude-code
stage: design
status: complete
created: 2026-11-06T01:24:25Z
updated: 2026-11-06T01:24:25Z
---

# Technical Design - Delete the Claude Code

Based on a read-only map of the tree after release A (`a4dde955` analysis, 2026-11-06).

## Step 1 (first pull request)

1. Move without change: `CodeOwnedSessionBootstrap` (+ `_decode_cookies`), `TypedObservation`,
   `_enum_value`, `_map_extracted_observation`, `build_trusted_search_url` from
   `agentic_executor.py`; `_price_entry_url` from `browser_use_price_executor.py`; the observation
   mappers and `_navigation_terminal` chain from `agentic_inventory_executor.py`, into neutral
   modules beside their users. Rewire `jev_price_executor`, `browser_use_inventory_executor`,
   `browser_use_runtime`, `session_maintenance`.
2. Delete `agentic_executor.py`, `browser_use_price_executor.py`, `agentic_inventory_executor.py`,
   `inventory_empty_state.py` if unused, and the Claude parts of `browser_use_runtime.py`
   (`budgeted_model_type`, `create_agent`, model envelope, guarded agent actions). The CLI price
   factory becomes Jev-only; `stagehand` leaves the dependencies.
3. Remove the paired comparison mode (coordinator arm, `application/price_comparison.py`, paired
   repository methods, `_make_jev_executor_factory`), keeping `jev_cost_since`, `JevPriceRun`,
   `JevComparisonSettings`, `JevUsage` and the Jev part of the report CLI.

## Step 2 (second pull request)

Delete the scripted price path (legacy parts of `search_check_job.py`, `search_journey.py`,
`browser_agent.py`, `room_table.py`, `dom_extract.py`, legacy trace methods), the legacy inventory
source (`booking_account_inventory.py`, `SynchronizeBookingAccount`, coordinator `_synchronize_user`;
an inactive user's sync fails instead), `llm/` except `typesafe_client.py`, the model-policy and
adaptive layer (keeping the DOM-incident enums and `UsdAmount`), `evaluation/` and its CLI,
`/setkey` and `/deletekey` with the key validator and dialogs, and the `anthropic` direct dependency.

## Test Plan

Each step: full suite (tests for deleted code removed), Ruff, mypy, an import check that nothing
imports `anthropic` or `stagehand`, and a live replay of the owner's, the dad's and the third
invitee's syncs plus the owner's Jev check.
