# Photo observation API (for the mobile app)

Crews register an observation of a photo target by tapping the button under the photo. The server scores it the
way a judge scores the line drawn across the track on a paper map.

## When registration is accepted

* The navigation task must have **Allow observation registration in the app** (`allow_observation_registration`,
  off by default, in the task settings and in the task serializer) switched on. With it off the API answers 403,
  nothing is scored, and unmarked photos are not misses, so paper-marked tasks are unaffected.
* For crew members the contestant must be one of the flights they are currently tracking: from its tracker start
  time until its finished-by time plus a grace period (12 hours, `OBSERVATION_REGISTRATION_GRACE_MINUTES`), so a
  queue built up offline can be sent once there is wifi after landing. The observation `time` must lie within the
  flight itself, not the grace period. A registration during the grace period replaces the "not marked" miss that
  was scored when the flight ended.
* Contest managers may register (e.g. to correct a record) regardless of the window and the flag; with the flag off
  the observation is stored but not scored.

## Photos to show

`GET /api/v1/contests/{contest_id}/navigationtasks/{task_id}/photos/?contestant={contestant_id}`
returns `id`, `name`, `file` (image URL) for each observation photo for that contestant. Register with the `id`.

### For crew: `GET /api/v1/contestant/{contestant_id}/observation_photos/`

The task photos endpoint above needs view or change permission on the contest unless the task is public, so a crew
member of a **private** task cannot use it. The app uses this endpoint instead: it is open to the contestant's crew
(and contest managers) whatever the visibility of the task. Photo images are served from public storage, so the `file`
URLs load without authentication.

```json
{"enabled": true, "may_register": true,
 "photos": [{"id": 123, "name": "A", "file": "https://.../a.jpg"}],
 "observations": [ ...the contestant's registrations, as in the list below... ]}
```

* `enabled` is the task option; `may_register` is whether the flight is being tracked now (including the grace period).
* `photos` has the registrable (non-decoy) photos, sorted by name, **without coordinates**.
* The "now" endpoint (`get_current_app_navigation_task`) tells the app whether to offer this with
  `observation_registration` on each active contestant.

## Register an observation

`POST /api/v1/contestant/{contestant_id}/photo_observations/` (authenticated; crew member or contest manager)

```json
{"photo": 123, "time": "2026-08-01T10:00:00Z", "latitude": 60.1, "longitude": 11.2}
```

* `photo` is the id of the photo marker (`id` in the photos list), not its name.
* `time` and the position are the crew's at the moment of the tap. Queue and retry offline: the call is idempotent
  per `(contestant, photo)`. A later `time` replaces an earlier registration (201), an equal or earlier one is
  ignored (200 with the stored observation), so replays are harmless.
* The response is the stored observation, including the score: `scored`, `status` (`ok`, `out_of_track`,
  `map_scale_unknown`, `no_route`), `error_mm`, `error_m`, `score_fraction`, `points` (the change to the
  contestant's score), `metres_per_mm` and the projected positions.

| Status | Meaning |
| --- | --- |
| 201 | Stored (new, or replacing an earlier registration). |
| 200 | Ignored: an equal or later registration already exists. |
| 400 | Invalid body, `photo` is not an observation photo of this flight, or `time` is outside the flight. |
| 403 | Not the crew or a manager, or the task does not allow observation registration. |
| 409 | The flight is not one the user is currently tracking (not started, or past the grace period). |

## List / delete

* `GET /api/v1/contestant/{contestant_id}/photo_observations/` lists the registrations (public for public tasks).
* `DELETE /api/v1/contestant/{contestant_id}/photo_observations/{id}/` (contest managers) removes one and reverses
  its score.

Changes are also pushed on the tracking websocket as a `photo_observations` message.

## Scoring

Both the crew position and the photo target are projected onto the contestant's route polyline (takeoff and landing
gates excluded). For the crew, only the photo's leg and its neighbours are considered. The distance along the track
between the two projections is converted to millimetres with `FlightOrderConfiguration.map_scale`
(1:N000 -> 1 mm = N00 m). "Fit page" and a missing configuration use 1:250,000.

| Task type | Rule | Scorecard field |
| --- | --- | --- |
| Legacy | Within 1 mm either side is a hit, anything else is a miss and costs the penalty. | `observation_photo_penalty` (default 100) |
| CIMA 2.A4 / 2.A5 | Qh = Vh * Nh: within 2 mm full, 2-5 mm half, more than 5 mm zero. | `observation_photo_value` (Vh, default 100) |

* The distances are configurable per scorecard with `observation_photo_full_tolerance_mm` and
  `observation_photo_half_tolerance_mm`; when blank the task type's rule above applies (the defaults are constants
  in `display/calculators/photo_observation_calculator.py`). The half band is never narrower than the full band.
* More than 20 mm from the track is `out_of_track` and scores zero.
* Photos that are never marked are misses when the flight ends.
* Scoring needs the task option above to be on. Other task types record observations but do not score them.
* For CIMA the deficit `Vh * (1 - score_fraction)` is applied on the same scale as the gate score,
  `initial_score * deficit / Qmax`, where Qmax includes `Vh * N` for the photos (`get_cima_gate_qmax`).
