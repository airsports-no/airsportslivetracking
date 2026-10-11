# Photo observation API (for the mobile app)

Crews register an observation of a photo target by tapping the button under the photo. The server scores it the
way a judge scores the line drawn across the track on a paper map.

## Photos to show

`GET /api/v1/contests/{contest_id}/navigationtasks/{task_id}/photos/?contestant={contestant_id}`
returns `id`, `name`, `file` (image URL) for each observation photo for that contestant.

## Register an observation

`POST /api/v1/contestant/{contestant_id}/photo_observations/` (authenticated; crew member or contest manager)

```json
{"photo": 123, "time": "2026-08-01T10:00:00Z", "latitude": 60.1, "longitude": 11.2}
```

* `photo` is the id of the photo marker (`id` in the photos list), not its name.
* `time` and the position are the crew's at the moment of the tap. Queue and retry offline: the call is idempotent
  per `(contestant, photo)`. A later `time` replaces an earlier registration (201), an equal or earlier one
  is ignored (200), so replays are harmless.
* Response is the stored observation including the score: `scored`, `status` (`ok`, `out_of_track`,
  `map_scale_unknown`, `no_route`), `error_mm`, `error_m`, `score_fraction`, `points` (the change to the contestant's score), `metres_per_mm` and the projected
  positions. 400 for a `photo` that is not an observation photo of the flight, 403 for anyone but the crew or a manager.

## List / delete

* `GET /api/v1/contestant/{contestant_id}/photo_observations/` lists the registrations (public for public tasks).
* `DELETE /api/v1/contestant/{contestant_id}/photo_observations/{id}/` (contest managers).

## Scoring

Both the crew position and the photo target are projected onto the contestant's route polyline (takeoff and landing
gates excluded). For the crew, only the photo's leg and its neighbours are considered. The distance along the track
between the two projections is converted to millimetres with `FlightOrderConfiguration.map_scale`
(1:N000 -> 1 mm = N00 m). "Fit page" and a missing configuration use 1:250,000.

| Task type | Rule | Scorecard field |
| --- | --- | --- |
| Legacy | Within 1 mm either side is a hit, anything else is a miss and costs the penalty. | `observation_photo_penalty` (default 100) |
| CIMA 2.A4 / 2.A5 | Qh = Vh * Nh: within 2 mm full, 2-5 mm half, more than 5 mm zero. | `observation_photo_value` (Vh, default 100) |

More than 20 mm from the track is `out_of_track` and scores zero. Photos that are never marked are misses when the
flight ends. Other task types record observations but do not score them.

For CIMA the deficit `Vh * (1 - score_fraction)` is applied on the same scale as the gate score, `initial_score *
deficit / Qmax`, where Qmax includes `Vh * N` for the photos (`get_cima_gate_qmax`). The distances are configurable per scorecard with `observation_photo_full_tolerance_mm` and
`observation_photo_half_tolerance_mm`; when blank the task type's rule above applies (the defaults are constants in
`display/calculators/photo_observation_calculator.py`). The half band is never narrower than the full band.
