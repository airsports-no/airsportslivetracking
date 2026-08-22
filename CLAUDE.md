# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Air Sports Live Tracking (ASLT) is an online live-scoring platform for aircraft competitions (precision flying, air navigation race, poker run, and other task types). It ingests live GPS position reports via Traccar, scores contestants in near-real-time, and serves results/tracking over HTTP and websockets.

## Architecture

**Hybrid backend/frontend.** Django serves "boring" CRUD, auth, and admin via server-rendered templates (`src/display/templates/`), while React (Vite) SPA components handle high-interactivity features (live map, route editor, dashboards). React apps are embedded into Django templates via Vite integration tags; built assets land in `assets_vite/` (see `outDir` in `react_vite/vite.config.js`), which Django serves from `/static/`.

**Three runtime processes** (see `docker-compose.yml`):
- `tracker_daphne`: Django web server (HTTP + websockets via Channels).
- `tracker_celery`: background jobs (track recalculation, flight order generation) via Celery.
- `tracker_processor`: standalone script (`src/position_processor.py`) that consumes position reports from Traccar/Redis and feeds them to the scoring engine.

In production these run as the `tracker-app`, `tracker-celery` and
`tracker-processor` deployments. `tracker-app` serves HTTP *and* websockets
from a single ASGI process (`config/asgi.sh` → gunicorn with the uvicorn
worker class in `src/live_tracking_map/uvicorn_worker.py`); it replaced a
separate `tracker-web` (gunicorn/WSGI) and `tracker-daphne` (daphne) pair.
Two Services still front it — `tracker-web-service` and
`tracker-daphne-service-gateway` — solely so `/ws` can keep its own
`GCPBackendPolicy` (3600s timeout) separate from ordinary HTTP; both select
the same pods. See `helm/templates/httproute_root.yaml`.

Position data flow: Traccar → Redis → `position_processor.py` → per-contestant `Orchestrator` (`src/display/calculators/orchestrator.py`) → Django Channels → websocket → frontend. The orchestrator coordinates specialized calculators (gate passing, corridor tracking, procedure turns, landing patterns, penalty zones, poker gates, etc. — see `src/display/calculators/`) and emits scoring events consumed elsewhere.

**Domain models** live under `src/display/models/` (one file per concern, re-exported from `models/__init__.py`): `Contest`, `NavigationTask`, `Contestant`, `Team`/`Crew`/`Person`/`Club`/`Aeroplane`, `Route`/`EditableRoute`, scorecards and gate scores, access control (`AccessGrant`, `ClubManagerMembership`, `TokenType`, `UserTokenGrant`, `ContestTokenAssignment`), and playing cards (poker task type).

**Scoring configuration** ("scorecards") define per-task-type rules and default values; see `src/display/default_scorecards/` for the built-in scorecards (FAI precision/ANR/rally, air sports challenge) and `src/display/services/task_compiler.py` / `contestant_task_compiler.py` for how navigation tasks get compiled from routes + scorecards into contestant-specific configurations.

**Access control / monetization**: contest capacity is governed by a resolved access tier (free tier, club pass, single-event grant, manual override, or token package). `ACCESS_ENFORCEMENT_MODE` (`audit` or `enforce`, see `settings.py`) controls whether limits are only surfaced or actually block actions. Resolution logic is in `src/display/services/access_resolver.py` and `capacity_enforcement.py`; relevant models are `AccessGrant`, `ClubManagerMembership`, `TokenType`, `UserTokenGrant`, `ContestTokenAssignment` (`src/display/models/access_control.py`, `usage_accounting.py`).

**CDN caching** (Google Cloud CDN) uses three independent invalidation layers — read `README.md`'s "Access control and free-tier configuration" section for the full semantics before touching cache headers or ETags:
1. Global app version — `SPECTACULAR_SETTINGS["VERSION"]` in `settings.py`.
2. Dashboard/list data version — `contest_list_version` in Redis, bumped by Django signals on `Contest`/`NavigationTask`/`Contestant` changes.
3. Per-contestant telemetry version — `track_version` on `Contestant`, used for `/slice/` ETag.

**Kubernetes calculator jobs**: `src/display/kubernetes_calculator/` can dispatch scoring/processing work as Kubernetes Jobs instead of running in-process — relevant when working on scaling or job orchestration.

## Common commands

### Local dev environment (Docker)
```bash
docker compose build                     # build all images
docker compose up tracker_daphne         # start web server + deps (mysql, redis, traccar) at http://localhost:8002/
```
Default superuser: `test@test.com` / `admin`. VS Code devcontainer + `tasks.json` automates the full stack (daphne, celery, processor, frontend watchers) if using the provided devcontainer.

### Backend tests (Django/pytest)
Tests run inside the `tracker_daphne` container (CI does the same via `docker exec`):
```bash
docker exec tracker_daphne pytest                                   # full suite
docker exec tracker_daphne pytest src/display/tests/test_foo.py     # single file
docker exec tracker_daphne pytest src/display/tests/test_foo.py::TestClass::test_method   # single test
docker exec tracker_daphne pytest --cov=. --cov-report=xml:reports/django_coverage.xml
```
`pytest.ini` sets `DJANGO_SETTINGS_MODULE=live_tracking_map.settings`, uses `--reuse-db`, and collects `tests.py`, `test_*.py`, `*_tests.py`. Backend tests live in `src/display/tests/`, `src/display/calculators/tests/`, `src/tests/`, and scattered `test_*.py` files near what they cover (e.g. `src/display/poker/test_poker_cards.py`).

### Backend lint/format (Python 3.12, ruff)
```bash
ruff check --fix --extend-select I .    # lint + import sort
ruff format .                            # format (double quotes, 120-char lines)
```
Config is in `pyproject.toml`; pre-commit (`.pre-commit-config.yaml`) runs ruff plus basic hygiene hooks (yaml/json/ast checks, trailing whitespace, EOF fixer).

### Frontend (React/Vite SPA) — `react_vite/`
```bash
cd react_vite && npm ci
npm run build          # production build -> ../assets_vite
npm run watch          # rebuild on change (used during local dev)
npm run dev             # vite dev server
npm run lint            # eslint
```
Also runnable from repo root via `npm run build:react` / `npm run watch:react` (see root `package.json`). React app entry points are auto-discovered from `.jsx`/`.tsx` files directly under `react_vite/src/` (see `vite.config.js`); feature code lives under `react_vite/src/features/<feature-name>/` (`competition-map`, `contest-results`, `mission-dashboard`, `route-editor`, `scheduling`). State uses `zustand`; routes are declared in `react_vite/src/routes.json`.

### Marketing/static site — `airsports_static/`
```bash
npm run build:marketing   # from repo root
npm run watch:marketing
```

### Tailwind CSS
```bash
npm ci
src/static/css/tailwindcss -i src/static/css/input.css -o src/static/css/output.css --watch
```
Tailwind v4 + DaisyUI v5 are used for styling; prefer utility classes/DaisyUI components over raw CSS.

### Icons
Lucide icons throughout: Django templates use `{% load lucide %}` + `{% lucide "icon-name" %}`; React uses `lucide-react`.

## Notes for making changes

- Env-driven settings (`src/live_tracking_map/settings.py`) distinguish dev (`MODE=dev`) from production; access-control enforcement, Firebase, and several external integrations (traccar, mbtiles, redis, mysql) are all configured via env vars with dev-friendly defaults for docker-compose.
- `documentation/` contains user manuals and API guides (some `.docx`, kept partly outdated per the README — prefer moving durable docs to the wiki rather than adding more files here).
- The GitHub wiki (linked from `README.md`) holds the model architecture and scoring-engine overview docs; consult it for deeper domain background before large model/calculator changes.
