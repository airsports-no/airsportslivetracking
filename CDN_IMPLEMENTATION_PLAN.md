# CDN High-Load & Universal Entry Point Implementation Plan

This document outlines the technical steps required to modernize the ASLT entry point and migrate mission-critical telemetry to be served via Google Cloud CDN.

---

## 1. Universal Entry Point Strategy (Hybrid)

The goal is to serve the high-performance Astro homepage at `airsports.no` while routing all application logic, including the integrated React app and Django management pages, to the existing backend.

### Domain Map
| Domain | Content | Hosting |
| :--- | :--- | :--- |
| `airsports.no` | Marketing & **Application Proxy** | Firebase Hosting + LB |
| `origin.airsports.no` | Django Backend, Scoring, Admin | GKE |

### Routing Logic (Load Balancer / Gateway)
The Global HTTP(S) Load Balancer will act as the primary router. To ensure zero disruption to the existing Django-integrated frontend, the following paths **MUST** be forwarded to the **GKE Backend**:

1.  **Core API & Admin:** `/api/*`, `/admin/*`, `/accounts/*`, `/firebase_login/*`
2.  **Legacy System:** `/display/*` (Includes Flymaster, health checks, and legacy views)
3.  **Application Modules:** (These handle both React and Django template views)
    *   `/mission-dashboard/*`
    *   `/competition-map/*`
    *   `/routeeditor/*`
    *   `/schedule-flight/*`
    *   `/schedule-contestants/*`
    *   `/upgrade-organizer/*`, `/upgrade-success/*`
4.  **Assets:** `/static/*`, `/media/*`
5.  **Default `/*`:** Forward to **Astro Homepage** (Firebase Hosting).

---

## 2. CDN Telemetry Architecture (High Load)

Instead of a full frontend decoupling, we focus on optimizing the data flow for high-concurrency events.

### A. Telemetry Minute-Slicing API
We will add new endpoints to Django specifically designed for edge caching:
1.  **Endpoint:** `/api/v1/contestant/<id>/slice/<minute_index>/`
2.  **Logic:** Returns GPS positions for a specific 60-second window.
3.  **Caching Strategy:** 
    *   **Completed Minutes:** `Cache-Control: public, max-age=31536000, immutable`.
    *   **Active Minute:** `Cache-Control: public, max-age=5, must-revalidate`.

### B. Dashboard Versioning
*   Append a version hash `?v=<hash>` to the contest list API.
*   Bumping the hash in Django instantly invalidates the CDN cache for all users when a contest is updated.

---

## 3. Implementation Phases

### Phase 1: Infrastructure Setup (Zero Risk)
1.  Provision a **Google Cloud Load Balancer** with a temporary Static IP.
2.  Configure the Load Balancer with two backends:
    *   **Primary:** GKE Cluster (Django).
    *   **Static:** Firebase Hosting (Astro Site).
3.  Implement the Path Rules defined in Section 1.

### Phase 2: Application Optimization
1.  Implement the `/slice/` API in Django.
2.  Update the React frontend (staying within the Django project) to "stitch" these slices together instead of polling the full track.
3.  Enable **Cloud CDN** on the Load Balancer for the `/slice/` path.

### Phase 3: Traffic Cutover
1.  Point the `airsports.no` DNS record to the new Load Balancer.
2.  The root domain now serves the Astro homepage, but clicking any app link (e.g., `/mission-dashboard/`) takes the user to the existing Django/React application seamlessly.

---

## 4. Advantages of this Approach
*   **No Code Migration:** The React app stays inside Django, using existing authentication, CSRF tokens, and template tags.
*   **Performance:** The marketing site is lightning fast and offloads all "landing" traffic from GKE.
*   **Scalability:** High-load telemetry is cached at the edge, allowing the system to handle thousands of spectators during major competitions.
*   **Compatibility:** All existing mobile app versions and hardware trackers (Flymaster) continue to work without modification.
