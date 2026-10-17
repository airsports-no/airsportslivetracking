# Plan: remove the global map leftovers

Status: implemented 2026-10-17 (phase 1 and the reduced phase 2: `Person.is_public` and `Person.last_seen` removed, migration `0198`). Written 2026-10-16.

## Finding: the global map itself is already gone

- No frontend shows a global traffic map, and `display.consumers.GlobalConsumer` (`ws/tracks/global/`) no longer exists: `display/routing.py`
  only routes `ws/traffic/airsports/` (it was removed in commit 148c6292). `CLAUDE.md` still describes `GlobalConsumer` and
  `transmit_global_position_data`; neither exists any more.
- Do not confuse it with `editableroutes-global-map-sources` (`viewsets.py:925`, used by the route editor): that is the list of background
  map sources for editing routes. It is unrelated and stays.

What is left is code and wording that still talk about "the global map", and one process that does more than its name says.

## What remains

| Where | What | Real function today |
|---|---|---|
| `position_processor.py`, `position_processor_process.py` | `global_map_queue`: every position (per contestant, and per person for devices without a contestant) is put on this queue | Feeds `live_position_transmitter_process` only |
| `live_position_transmitter.py` | A separate process (`live_position_transmitter`) | (a) The outbound partner feed `ws/traffic/airsports/` (`transmit_airsports_position_data`, non-simulator positions only, max 60 s old). (b) Writes `Person.last_seen` on **every position** (one DB save each) |
| `Person.last_seen` | Field | Written only. No code reads it, but check API serialisers that expose all fields |
| `Person.is_public` | "name displayed with the callsign on the global map" | Only reset on account deletion. No reader |
| `Person.app_aircraft_registration` | Callsign | Used only by the partner feed for devices that have no contestant |
| Help texts and docs | `Person.simulator_tracking_id`, `Person.is_public`, `ContestSettingsForm.tsx` ("Visible on the global map and in contest listings"), `user_guide/03_Contest_Manager_Guide.md`, `airsports_static/.../03_Contest_Manager_Guide.md`, `CLAUDE.md`, comments in `consumers.py` | Describe a map that does not exist |
| Tests | `tests/test_position_processor.py` asserts `global_map_queue.put` calls | Rename with the queue |

## Decision: SafeSky still consumes the partner feed

Confirmed 2026-10-16: SafeSky still consumes `ws/traffic/airsports/`. The transmitter process, the feed, `AirsportsPositionsConsumer`
and `Person.app_aircraft_registration` therefore **stay**. Phase 2 is reduced to its last item below.

## Phase 1: safe cleanup (needed whatever the answer is)

1. Rename `global_map_queue` to something honest (for example `transmitter_queue`) throughout, and update the comment in
   `position_processor.py` that says "to appear on the global map and on the air sports data feed". Update the test.
2. Correct the help texts and documentation listed above: public contests are "listed publicly", not "on the global map".
3. Fix `CLAUDE.md`: remove `GlobalConsumer` and `transmit_global_position_data`.
4. Decide on `Person.is_public`: remove it (migration, `account_deletion.py`, `views.py:304`, and the test), after confirming no API client
   (website, mobile apps, MSFS client) reads or writes it.

## Phase 2 (reduced): keep the feed, drop what only served the map

The transmitter stays because of the SafeSky feed. What can still go:

1. The `Person.last_seen` write on every position (one DB save per received position), if nothing needs it. Check serialisers and API
   consumers (website, mobile apps, MSFS client) first; then remove the field with a migration.
2. Nothing else in the transmitter is map-specific once the queue is renamed (phase 1), so keep it as it is.

## Order and checks

- Phase 1 as one small change with a changelog line only if it touches mobile or MSFS clients (the changelog is for mobile-related changes).
- Before phase 2: check what reads `Person.last_seen` (including API output).
- Targeted tests only: `tests/test_position_processor.py`, the account deletion test, and the serialiser tests that include `Person`.
- Coordinate with `PLAN_simulator_separation.md`: that plan's ingest filter lives in the same function, so do phase 1's queue rename first.
