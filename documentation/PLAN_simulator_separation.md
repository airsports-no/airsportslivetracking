# Plan: separating simulator flights from real flights

Status: planned, nothing implemented. Written 2026-10-16.

## Problem

The MSFS client (in-game panel, quick-start competition) and the planned marketing to the flight simulation community will bring
many simulator pilots. A real pilot only registers for a task they will fly, because they have to go to the airport. A simulator
pilot can register for any open self-managed task and fly it at home, which pollutes national cups, results and the live map, and
adds load (every tracked contestant runs a live calculator, see `display.tasks.run_live_contestant_calculator`).

## What exists today

- `Person.simulator_tracking_id` and `Person.app_tracking_id` are separate Traccar device ids. A pilot has both.
- `Contestant.get_contestant_for_device_at_time` returns `(contestant, is_simulator)` for each incoming position.
- `Contestant.has_been_tracked_by_simulator` is set once, in `position_processor_process.cached_find_contestant`, when the first simulator
  position arrives. It is only a label, used to highlight the contestant in the dashboard. Nothing is blocked.
- Registration is gated only by `NavigationTask.allow_self_management` (plus public visibility and the task's time window).
- The simulator client will send `X-App-Platform: msfs` (see `msfs_client_port_plan.md`, `mobile_app_activity.py`).

## Key design constraint

At registration or scheduling time we cannot tell whether the pilot will fly for real or in the simulator: the registration belongs to a
person, who owns both ids. **The tracking data is the only reliable signal**, so enforcement happens where positions arrive.
Registration-time information is used only to warn and to guide, never to decide.

## Design

### 1. Simulator policy per navigation task

New field `NavigationTask.simulator_policy`, three values:

| Value | Meaning |
|---|---|
| `not_allowed` | Simulator positions are dropped. **Default**, also for all existing tasks (migration sets every existing row to this). |
| `allowed` | Simulator flights are accepted under the normal rules and badged as simulator flights (see 4). |
| `simulator_only` | Only simulator positions are accepted. Real tracker and app positions are dropped. For the simulator playground and the quick start (see 2). |

Exposed in the task form, the React task modals and the task serialisers, next to "allow self management".

### 2. The simulator playground (organizer content, not platform code)

A public contest, built by the platform owner as an ordinary organizer, with a selection of tasks set to `simulator_only` (or `allowed`).
It is an unofficial playground and "simulator cup" where simulator pilots compete on skills until other organizers take it up.

- Tasks are always open by giving them a `finish_time` far in the future. No rolling job, no "always open" flag, no special handling in the
  platform or the apps. Other organizers can build their own simulator contests the same way.
- This is separate from the MSFS **quick start**, which already exists (`SimulatorQuickstart`, `services/simulator_quickstart.py`, the
  `msfs_quickstart` endpoints, on `origin/main` since PR #818). It points at one navigation task. Interplay with the policy: the
  quick start's task must not be `not_allowed`, or the pilot registers in one press and every position is then silently dropped.
  So `current_quickstart` only offers a quick start whose task allows simulators, and the admin refuses (or warns about) a quickstart
  whose task is `not_allowed`. `simulator_only` is the natural policy for it.
- Platform work this needs: only the policy field (1) and the enforcement (3). Check that a far-future `finish_time` has no side effects
  (task listings and sorting, the open-task counts, the calculator pool pre-warm lookahead, any "upcoming" notifications).

### 3. Enforcement at position ingest

In `position_processor_process.cached_find_contestant`, after the contestant tuples are found, filter the `active_tuples`:

- policy `not_allowed` and `is_simulator`: drop.
- policy `simulator_only` and not `is_simulator`: drop.

Dropped silently: no calculator is started, nothing goes to the global map queue, nothing is stored.
The existing once-per-contestant write is the model for the only trace we keep: a small field on the contestant, for example
`blocked_simulator_positions_at` (first time seen), written once, used to
- show the organizer a notice on the contestant ("simulator positions received and ignored"), and
- let the app/client tell the pilot why nothing shows up (see 5).

The contestant cache (`contestant_cache`, `CACHE_TTL`) means a policy change takes effect after at most the TTL. State that in the field's help text.
This also has to cover the traccar facade path (`traccar_facade.py` uses both id lists) and any other consumer of `get_contestant_for_device_at_time`;
step 1 of the implementation is to list every caller.

### 4. Badging where simulators are allowed

Where simulator flights are allowed, they follow exactly the same rules as regular flights (live map, scoring, results, ranking). The only
difference is a clear **simulator badge**:

- A contestant with `has_been_tracked_by_simulator` is badged as a simulator flight in the dashboard, the live map, the results and the app.
  A flight that gets both real and simulator positions is a simulator flight (any simulator position).
- No separate class, no exclusion from rankings. The global map and the external traffic feed already exclude simulator contestants (they
  are not real traffic). Keep that.

### 5. Declared flight intent at registration

Because only the tracking data shows what a pilot really does, the registration should also capture what they *say* they will do.

- New field `Contestant.flight_mode`: `real` or `simulator`, nullable (null = flights that existed before this feature; they are
  governed by the task policy alone).
- Self-registration (`SelfManagementSerialiser`, `create_self_managed_contestant`, shared by the website and the apps) takes the intent:
  - **Website:** a required drop-down "How will you fly this?", empty by default, so the pilot has to decide. Options: "In a real aircraft
    (tracked by the app or a tracker)" and "In a flight simulator". The text explains the consequence of a wrong choice (below). Options
    the task's policy does not allow are disabled with the reason, so a `not_allowed` task shows that simulators are not accepted before
    the pilot goes any further.
  - **MSFS client and phone apps:** no drop-down. The server sets the intent from `X-App-Platform` (`msfs` = simulator, `android`/`ios` = real)
    and these clients only list tasks whose policy suits them. The one-press quick start sets `simulator`.
    **Caveat found while checking:** the apps register through the website's "Register today" page in a web view (`embed=app`), and
    those page loads carry no `X-App-Platform` (only the first `firebase_login` request has an `Authorization` header). The server can
    tell "an app web view" (`request.embed_app`) but not which client. Fix (small, one line per client): the clients also send their
    platform when opening web pages (for example `embed=app&client=msfs|android|ios`, or the `X-App-Platform` header on the
    `firebase_login` request), and `EmbedModeMiddleware` keeps it in the embed cookie. Clients without the change (old builds, unknown
    client) simply get the drop-down inside the web view: correct, only redundant. The native API calls already carry the header.
    Places to change: MSFS client `msfsclient.Core/Api/Urls.cs` `WithEmbedFlag` (line ~85, used by `FirebaseLoginUrl`) with its test in
    `msfsclient.Core.Tests/ApiTests.cs` (~line 494); mobile app `WithEmbedFlag` in `shared/.../ui/WebScreen.kt` (and its tests); server
    `EmbedModeMiddleware` in `live_tracking_map/middleware.py`.

  - **Organizer-created contestants** (not self-registered): the contestant form gets the same field; for `not_allowed` and
    `simulator_only` tasks it is preset from the policy, for `allowed` tasks the organizer picks.
- **Registration is refused** when the intent conflicts with the policy (a clear error, nothing created).
- **Enforcement uses the intent as well as the policy** (section 3): a contestant with intent `real` ignores simulator positions and a
  contestant with intent `simulator` ignores real tracker and app positions, so a flight is never a mix and cannot be tracked twice.
  Positions ignored this way set the same one-time trace field as a policy drop. The badge (section 4) follows the declared intent.
- Text on the drop-down (draft): "Choose carefully. If you choose *real aircraft* and then fly in a simulator, your simulator
  positions are ignored and your flight is not recorded. If you choose *simulator* and then fly a real aircraft, your tracker positions
  are ignored. Simulator flights are marked as such in the results."
- Limit: the drop-down cannot stop someone who lies; it makes the choice active, gives a clear error up front, and makes the
  consequence of a wrong choice explicit.

## Limits

- A determined pilot can feed simulator positions through the app id. That is a spoofing problem, covered by `PLAN_signed_position_reports.md`,
  and not solved here. This plan stops honest mistakes and drive-by flights.
- A pilot with a real flight and a sim flight on the same task and time is a corner case; the device id decides per position.

## Implementation order

1. Audit callers of `get_contestant_for_device_at_time`, `get_simulator_tracker_ids` and `has_been_tracked_by_simulator`.
2. Model fields `simulator_policy` and `Contestant.flight_mode` and migration (all existing tasks to `not_allowed`), serialisers, forms, React modal. The quick start only offers, and the admin only accepts, tasks that allow simulators.
3. Ingest filter and the contestant trace field, with tests for each policy and for the cache.
4. Check the far-future `finish_time` side effects. Then you create the playground contest and the quick-start contest as organizer content.
5. Registration intent (serialiser, service, website drop-down, platform-derived intent for the clients), the simulator badge, registration page warning, client/app list filtering and the "not recorded" message.
6. Admin visibility: count of dropped simulator flights per task.
7. Mobile and backend change log entries (`documentation/mobile_changelog.md`).

## Open questions

None at the moment. Both earlier questions are settled: simulator flights on `allowed` tasks follow the normal rules with a badge, and the
quick start is the existing `SimulatorQuickstart` model and endpoint.

## Note for implementation

Local `main` in `/home/kolaf/dev/airsportslivetracking` lags `origin/main` (the quick start is only on `origin/main`). Branch from
`origin/main`.
