# Photo observation API (for the mobile app)

Crews register an observation of a photo target by tapping the button under the photo. The server scores it the
way a judge scores the line drawn across the track on a paper map.

## Photos to show

`GET /api/v1/contests/{contest_id}/navigationtasks/{task_id}/photos/?contestant={contestant_id}`
returns `id`, `name`, `file` (image URL) for each observation photo for that contestant.

## Register an observation

`POST /api/v1/contestant/{contestant_id}/photo_observations/` (authenticated; crew member or contest manager)

```json
{"photo_name": "A", "time": "2026-08-01T10:00:00Z", "latitude": 60.1, "longitude": 11.2}
```

* `time` and the position are the crew's at the moment of the tap. Queue and retry offline: the call is idempotent
  per `(contestant, photo_name)`. A later `time` replaces an earlier registration (201), an equal or earlier one
  is ignored (200), so replays are harmless.
* Response is the stored observation including the score: `scored`, `status` (`ok`, `out_of_track`,
  `map_scale_unknown`, `no_route`), `error_mm`, `error_m`, `score_fraction`, `metres_per_mm` and the projected
  positions. 400 for an unknown `photo_name`, 403 for anyone but the crew or a manager.

## List / delete

* `GET /api/v1/contestant/{contestant_id}/photo_observations/` lists the registrations (public for public tasks).
* `DELETE /api/v1/contestant/{contestant_id}/photo_observations/{id}/` (contest managers).

## Scoring

Both the crew position and the photo target are projected onto the contestant's route polyline (takeoff and landing
gates excluded). For the crew, only the photo's leg and its neighbours are considered. The distance along the track
between the two projections is converted to millimetres with `FlightOrderConfiguration.map_scale`
(1:N000 -> 1 mm = N00 m; "Fit page" is estimated from the route extent and paper size).
`score_fraction` is 1 within 1 mm either side, otherwise 0; more than 20 mm from the track is `out_of_track`.
Tolerances are constants in `display/calculators/photo_observation_calculator.py`.
