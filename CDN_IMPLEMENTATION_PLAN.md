# CDN High-Load & Universal Entry Point Implementation Plan

This document outlines the technical steps required to modernize the ASLT entry point and migrate mission-critical telemetry to be served via Google Cloud CDN.

---

## 1. Universal Entry Point Strategy (Hybrid)

The goal is to serve the high-performance Astro homepage at `airsports.no` while providing a dedicated, user-friendly application domain at `app.airsports.no`.

### Domain Map
| Domain | Content | Hosting |
| :--- | :--- | :--- |
| `airsports.no` | Marketing & **Application Proxy** | Google Cloud LB + CDN |
| `app.airsports.no` | **Direct Application Access** | Google Cloud LB + CDN |

### Routing Logic (Global Load Balancer)
The Load Balancer acts as the intelligent gateway for both domains, routing directly to the GKE Backend Service (via NEGs).

#### A. Host: `app.airsports.no` (The App)
This domain preserves the original ASLT experience where the dashboard is at the root.
1.  **Paths `/*`:** Forward to **GKE Backend Service**.
2.  **Asset Offloading:** `/static/*` and `/media/*` should still be routed to GCS Backend Buckets for performance.

#### B. Host: `airsports.no` (The Portal)
1.  **Default `/*`:** Forward to **Astro Homepage** (Firebase Hosting).
2.  **Application Routing:** The following paths are proxied to the **GKE Backend Service** to ensure a seamless "one-site" feel:
    *   `/api/*`, `/admin/*`, `/accounts/*`, `/firebase_login/*`
    *   `/display/*`
    *   `/mission-dashboard/*`, `/competition-map/*`, `/routeeditor/*`
    *   `/schedule-flight/*`, `/schedule-contestants/*`
    *   `/upgrade-organizer/*`, `/upgrade-success/*`

---

## 2. Completed Application Optimizations (Phase 2) ✅

The application codebase is now fully CDN-ready. The following has been implemented:

### A. Telemetry Minute-Slicing & Chunking API
1.  **Endpoint:** `/api/v1/contestant/<id>/slice/<minute_index>/?count=15`
2.  **Efficiency:** Supports **aligned 15-minute chunks** to reduce origin requests by 15x.
3.  **Invalidation:** ETags based on `track_version` allow surgical cache clearing for specific pilots.

### B. Dashboard Versioning & ETag Strategy
1.  **Clean URLs:** Removed `?v=` hashes in favor of stable URLs with ETag validation.
2.  **Performance:** Integrated `stale-while-revalidate` for public lists to ensure zero-latency spectators.

### C. CDN Safety Middleware
1.  **Security:** Forces `Vary: Authorization, Cookie` on all API responses.
2.  **Protection:** Defaults all non-public API endpoints to `private, no-cache`.

---

## 3. Infrastructure Implementation Guide (Phase 1 & 3) 🚀

### Step 1: Configure Load Balancer Frontends
1.  Reserve a Global Static IP.
2.  Create Managed SSL certificates for:
    *   `airsports.no`
    *   `app.airsports.no`

### Step 2: Set Up Backend Buckets & Origins
1.  **Static-Bucket:** Point to `airsports-static` GCS (Mode: `FORCE_CACHE_ALL`).
2.  **Media-Bucket:** Point to `airsports-data` GCS (Mode: `FORCE_CACHE_ALL`).
3.  **Astro-Origin:** Create Internet NEG for the Firebase Hosting domain.
4.  **GKE-Origin:** Point to the existing GKE NEG (Mode: `USE_ORIGIN_HEADERS`).

### Step 3: URL Map & Routing Rules
Define the following Host/Path rules:

**Host: `app.airsports.no`**
*   `/static/*` -> `Static-Bucket`
*   `/media/*` -> `Media-Bucket`
*   `/*` (Default) -> `GKE-Origin`

**Host: `airsports.no`**
*   `/static/*` -> `Static-Bucket`
*   `/media/*` -> `Media-Bucket`
*   `/api/*`, `/admin/*`, etc. (See Section 1B) -> `GKE-Origin`
*   `/*` (Default) -> `Astro-Origin`

### Step 4: Final Cutover
1.  **DNS:** Update A records for `airsports.no` and `app.airsports.no` to the LB Static IP.
2.  **Allowed Hosts:** Ensure `app.airsports.no` is added to `ALLOWED_HOSTS` in Django settings.
3.  **CORS/CSRF:** Update `CSRF_TRUSTED_ORIGINS` to include `https://app.airsports.no`.

---

## 4. Advantages of this Approach
*   **User Choice:** Power users can use `app.airsports.no` for the direct dashboard experience.
*   **Marketing Impact:** `airsports.no` serves a lightning-fast Astro landing page.
*   **Shared Performance:** Both domains benefit from the same CDN-optimized telemetry and asset offloading.
