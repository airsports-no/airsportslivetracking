# Air Sports Live Tracking (ASLT) - AI Context

## Project Overview
ASLT is a platform for live tracking and scoring of air sports competitions (Precision Flying, Air Navigation Racing). It provides real-time position tracking, automated scoring based on complex rules, and visualization for organizers and spectators.

## Tech Stack

### Backend
*   **Language:** Python 3.12+
*   **Framework:** Django 6.0.1
*   **API:** Django REST Framework (DRF) + `drf-spectacular` (OpenAPI)
*   **Async/Real-time:**
    *   **Celery:** Background task processing (scoring, flight order generation).
    *   **Django Channels (Daphne):** Websockets for live tracking updates.
*   **Database:** MySQL (Primary), Redis (Cache, Celery Broker, Channel Layer).
*   **Key Libraries:** `numpy`, `pandas`, `scipy` (calculations), `shapely`/`geopy` (GIS), `lucide` (Icons).

### Frontend
*   **Architecture:** Hybrid.
    *   **Django Templates:** Server-side rendering for management, CRUD operations, and static pages.
    *   **React (Vite):** Single Page Application (SPA) components for complex interactive features (Map visualization, Route Editor, Dashboard).
*   **Styling:** Tailwind CSS v4 + DaisyUI v5.
*   **Maps:** Leaflet, OpenStreetMap, MBTiles support.
*   **Icons:** Lucide Icons (`lucide-react` for React, `lucide[django]` for Templates).

### Infrastructure
*   **Containerization:** Docker & Docker Compose.
*   **Orchestration:** Kubernetes (Helm Charts provided).
*   **Cloud:** Designed for Google Cloud Platform (GCP) but portable.
*   **Tracking Server:** Integrates with **Traccar** for GPS data ingestion.

## Key Design Choices

1.  **Split Frontend:** The project uses Django templates for "boring" CRUD views to leverage Django's productivity (forms, auth, admin), while reserving React for high-interactivity domains (maps, live dashboards).
    *   *Convention:* React apps are embedded into Django templates using Vite integration tags.
2.  **Scoring Engine:** Scoring logic is decoupled from the web view, likely running in Celery tasks or separate processor processes (`tracker_processor`) to handle high-frequency GPS data without blocking the web server.
3.  **Real-time Data:** Position updates flow from Traccar -> Redis -> Django Channels -> Websocket -> Frontend Client.
4.  **Domain Models:** The domain is modeled around `Contest`, `NavigationTask` (a specific flight/route), `Contestant`, `Team`, and `Track` data.

## Project Structure (Key Paths)

*   `/src/`: Django Backend Root.
    *   `live_tracking_map/`: Project settings, URL routing, ASGI/WSGI config.
    *   `display/`: Core app.
        *   `models/`: Domain models (Contest, Team, NavigationTask, etc.).
        *   `calculators/`: Scoring logic.
        *   `templates/`: Django HTML templates.
        *   `views.py`, `api.py`: View logic.
    *   `position_processor.py`: Standalone script for processing incoming tracker data.
*   `/react_vite/`: React Frontend Root.
    *   `src/features/`: Feature-based folder structure (mission-dashboard, route-editor, etc.).
*   `/conductor/`: Documentation and architectural guides.
*   `/docker-compose.yml`: Local development services definition.

## Development & Operational Commands

*   **Start Local Dev:** `docker-compose -f docker-compose.yml up`
*   **Frontend Dev:** `npm run build -m dev` (inside `react_vite/`) - usually proxied or integrated via Django settings in dev mode.
*   **Database:** MySQL running on port 3306.
*   **Redis:** Running on port 6379.

## Code Conventions

*   **Icons:** Use Lucide icons.
    *   *Django:* `{% load lucide %}` -> `{% lucide "icon-name" class="..." %}`
    *   *React:* `import { IconName } from 'lucide-react';`
*   **Styling:** Use Utility classes (Tailwind) + DaisyUI components. Avoid raw CSS.
*   **Formatting:** Python uses Black/Flake8 (implied by config). Frontend uses Prettier/ESLint.

## Critical Files for AI Reference
*   `src/live_tracking_map/settings.py`: Configuration source.
*   `src/display/models/`: Source of truth for data structures.
*   `react_vite/package.json`: Frontend dependency truth.
*   `docker-compose.yml`: Service relationship map.
