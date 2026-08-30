---
stage: design
bolt: 060-agentic-inventory-executor
created: 2026-08-30T18:08:00Z
---

# Technical Design: Browser Use `/bookings` Inventory Executor

## Architecture Pattern

Add a second infrastructure adapter behind the existing `InventoryBrowserExecutor` port and select
it at the coordinator boundary only when the synchronization trigger is `BOOKINGS`. The adapter is
local, transient, provider-neutral above infrastructure, and terminal on failure. Existing
application validation, positive-only reconciliation, metrics, refreshed-session verification,
Stagehand routing, legacy rollback, and price execution remain unchanged.

Use Browser Use `0.11.13`, the last established classic-agent release whose declared Anthropic range
is compatible with BookSaver's installed SDK. Pin the package exactly and declare its omitted
`pydantic-settings` runtime dependency explicitly. Do not force-install current `0.13.x`, which
hard-pins an incompatible Anthropic version, and do not use beta agent APIs.

## Layer Structure

- **Domain**: Add only a Browser Use inventory observation source. Existing inventory request,
  result, session lease, usage, provenance, and terminal types remain unchanged.
- **Application**: Reuse `InventoryBrowserExecutor`, `InventoryExecutionService`, the observation
  validator, and positive-only reconciliation without provider imports.
- **Coordinator**: Inject a separate `bookings_inventory_executor_factory`; select it only for
  `SynchronizationTrigger.BOOKINGS`, then pass the selected factory into the existing agentic
  synchronization flow. No same-job fallback follows a Browser Use terminal.
- **Browser Use adapter**: Own lazy library import, transient browser lifecycle, owner-bound cookie
  bootstrap, guarded custom tools, bounded model proxy, typed evidence collection, terminal mapping,
  refreshed-cookie eligibility, and unconditional teardown.
- **Composition root**: Build both inventory factories: Browser Use for `/bookings`, Stagehand for
  connect/check-now/scheduled work. Reuse the same trusted mobile settings, lease broker, Anthropic
  key, thread-scoped cost budget, and installed Chromium.

## Dependency and Import Design

- Pin `browser-use==0.11.13` and a compatible exact `pydantic-settings` release in the Python package
  and lock/container build.
- Set `ANONYMIZED_TELEMETRY=false`, Browser Use cloud/version-check flags, and content-persistence
  controls in the process/container environment before any Browser Use module import.
- Keep Browser Use imports inside the adapter bootstrap so ordinary commands and Stagehand routes do
  not initialize its global services.
- At startup, compare the effective registered action names with the closed qualified allowlist and
  fail closed if an upgrade or transitive change adds a default action.

## Browser and Session Design

The local adapter launches one fresh Chromium/profile with BookSaver's configured mobile identity,
injects only the leased cookies through local browser APIs, and navigates only to the code-owned
Booking.com inventory entry. Browser Use attaches locally to that browser/session; cookies never
enter its task, model messages, result, logs, or metrics.

Browser Use's stock popup/dialog automation is not authoritative. The adapter removes or disables
automatic popup acceptance before any tab becomes interactive, installs a local handler that always
dismisses `confirm` and `prompt`, and accepts no popup/new-tab action. Unexpected tabs close and
terminate the episode. Browser/profile teardown runs for success, failure, cancellation, timeout,
budget exhaustion, and provider error.

## Agent and Tool Design

The established agent receives a narrow inventory-perception task and exactly these BookSaver-owned
tools:

- `guarded_click(index)`: inspect the indexed live element; deny authentication, challenge,
  credential, mutation, cancellation, reservation, checkout, purchase, payment, download, external,
  popup, or suspicious intent; execute one click; recheck destination/dialog/tab state.
- `guarded_scroll(direction)`: one bounded viewport scroll with post-state checks.
- `guarded_key(key)`: only `PageUp`, `PageDown`, `Home`, `End`, and `Escape`.
- `guarded_wait(seconds)`: bounded wait within the absolute deadline.
- `submit_inventory_observation(payload)`: collect a bounded provider-shaped positive observation;
  it has no persistence or reconciliation authority.
- `done(payload)`: close with typed scope evidence after positive submissions or one closed
  non-success terminal.

All stock navigation, typing, form, tab, file, shell, clipboard, upload/download, credential,
search, and mutation-capable actions are removed. The agent executes at most one action per step and
cannot exceed the request's residual action count or absolute deadline.

## Guard Design

Observation and interaction authority remain separate under ADR-040. HTTPS Booking.com content may
be observed unless it has known authentication, challenge, transaction, or mutation intent.
Interaction requires inspected live metadata and rejects a compact code-owned set of unsafe
intent/path terms. It does not require exact safe labels, CSS selectors, test IDs, or read-only route
names. Current, target, and post-action destinations, new tabs, downloads, and dialogs are checked on
every action. Provider descriptions and page instructions cannot grant authority.

## Model and Cost Design

A BookSaver model proxy wraps every physical Anthropic call. Before forwarding it reserves that
call through the existing `BrowserJobCostBudget`; afterward it reconciles actual input/output/cache
usage even when the call partially fails. It reports aggregate `ExecutionUsage` through the existing
result type. Agent steps are serial, `max_actions_per_step=1`, and residual action/deadline values
bound the episode. No independent Browser Use retries may create an unaccounted model call.

## Result and Failure Design

Provider-shaped submissions decode into existing `ObservedReservation` and
`ObservedInventoryScope` values with bounded collections and no domain conclusions. Existing
BookSaver validation decides what is accepted. Missing terminal submission, malformed data,
signed-out, MFA, CAPTCHA, bot wall, unsafe action, budget exhaustion, action limit, timeout, browser
failure, and provider failure map to closed existing inventory terminals. No content-bearing
exception text crosses the adapter.

Only BookSaver's existing code-owned protected-resource authentication proof can make refreshed
cookies eligible. A model claim cannot. Browser Use provenance is recorded as a new closed
observation source; existing unconstrained redacted metrics storage requires no schema migration.

## Privacy and Egress Design

Disable anonymous telemetry, cloud sync, version checks, remote logs, conversation/history export,
GIF/video, HAR, trace, and screenshot persistence before import. Do not persist task text, DOM,
screenshots, action history, selectors, prompts, reasoning, raw URLs, provider exceptions, or
cookies. Authenticated execution may contact only Booking.com application hosts, Booking.com's
`bstatic.com` static-delivery hosts, Anthropic, and loopback.

## Test Design

- Contract/adapter tests: exact dependency/API, lazy import controls, action registry equality,
  one-action steps, typed partial positives, every terminal, malformed submissions, usage/cost,
  absolute deadline, lease binding, session refresh proof, and teardown.
- Safety tests: all unsafe default tools absent; unsafe labels/paths/destinations/popups/downloads,
  prompt/confirm dialogs, new tabs, post-action changes, and prompt-injection requests rejected.
- Routing tests: `/bookings` constructs Browser Use only; connect/check-now/scheduled construct
  Stagehand; price unchanged; Browser Use terminal never cascades to another executor.
- Privacy tests: secrets absent from task/config/result/repr/logs and no content artifacts remain.
- Resilience tests: classes, test IDs, nesting, overlays, accessibility text, and benign read-only
  route/label changes do not require a BookSaver selector or exact safe-label update.
- Container tests: clean resolution with Stagehand/Anthropic, non-root Chromium launch/attach,
  complete fake typed agent episode, teardown, content-artifact scan, and egress confinement.
