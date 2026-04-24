# CDN High-Load & Universal Entry Point Implementation Plan

This document outlines the technical steps required to modernize the ASLT entry point and migrate mission-critical telemetry to be served via Google Cloud CDN.

---

## 1. Universal Entry Point Strategy (Hybrid)

The goal is to serve the high-performance Astro homepage at `airsports.no` while routing all application logic, including the integrated React app and Django management pages, to the existing backend.

### Domain Map
| Domain | Content | Hosting |
| :--- | :--- | :--- |
| `airsports.no` | Marketing & **Application Proxy** | Google Cloud LB + CDN |
| `origin.airsports.no` | Django Backend, Scoring, Admin | GKE Ingress (Legacy) |

### Routing Logic (Load Balancer / Gateway)
The Global HTTP(S) Load Balancer will act as the primary router.

1.  **GKE Backend (Django/React):**
    *   `/api/*`, `/admin/*`, `/accounts/*`, `/firebase_login/*`
    *   `/display/*`
    *   `/mission-dashboard/*`, `/competition-map/*`, `/routeeditor/*`
    *   `/schedule-flight/*`, `/schedule-contestants/*`
    *   `/upgrade-organizer/*`, `/upgrade-success/*`
2.  **Static Assets (GCS Backend Bucket):**
    *   `/static/*` (Backend: `airsports-static`)
    *   `/media/*` (Backend: `airsports-data`)
3.  **Default `/*`:** 
    *   Forward to **Astro Homepage** (Firebase Hosting).

---

## 2. Completed Application Optimizations (Phase 2) ✅

The application codebase is now fully CDN-ready. The following has been implemented:

### A. Telemetry Minute-Slicing & Chunking API
1.  **Endpoint:** `/api/v1/contestant/<id>/slice/<minute_index>/?count=15`
2.  **Logic:** Returns GPS positions for a specific window. Supports **aligned 15-minute chunks** to reduce requests by 15x while maintaining CDN cache hit consistency.
3.  **Surgical Invalidation:** Uses ETags based on `track_version`. Uploading a GPX instantly invalidates all cached slices for that pilot globally.

### B. Dashboard Versioning & ETag Strategy
1.  **Global Versioning:** Signals automatically increment a `contest_list_version` in Redis on any dashboard change.
2.  **Clean URLs:** Removed `?v=` hashes from URLs in favor of standard HTTP ETags. This prevents "Thundering Herd" origin hits while allowing instant invalidation.

### C. CDN Safety Middleware
1.  **Vary Headers:** Every API response now includes `Vary: Authorization, Cookie`. This prevents the CDN from accidentally serving one user's private data to another.
2.  **Private-by-Default:** Any API endpoint not explicitly optimized for public caching defaults to `private, no-cache`.

---

## 3. Infrastructure Implementation Guide (Phase 1 & 3) 🚀

This phase involves setting up the Google Cloud environment to act as the "Shield" for the backend.

### Step 1: Create Global HTTP(S) Load Balancer
1.  **Frontend Configuration:**
    *   Create a global IP address (Static).
    *   Assign a managed SSL certificate for `airsports.no`.
2.  **Backend Services:**
    *   **GKE-Backend:** Point to the existing GKE Service (via Network Endpoint Group/NEG).
    *   **Static-Bucket:** Create a "Backend Bucket" pointing to `airsports-static`.
    *   **Media-Bucket:** Create a "Backend Bucket" pointing to `airsports-data`.
    *   **Astro-External:** Configure a "Custom Origin" (Internet NEG) pointing to the Firebase Hosting domain.

### Step 2: Configure Routing Rules (URL Map)
Implement the host and path rules:
*   Rule 1: Path `/static/*` -> `Static-Bucket`
*   Rule 2: Path `/media/*` -> `Media-Bucket`
*   Rule 3: All application paths (Section 1) -> `GKE-Backend`
*   Rule 4: Default `/*` -> `Astro-External`

### Step 3: Enable Cloud CDN
1.  **Enable CDN** on the following backends:
    *   `Static-Bucket`: Set "Cache mode" to `FORCE_CACHE_ALL`.
    *   `GKE-Backend`: Set "Cache mode" to `USE_ORIGIN_HEADERS` (This respects the `stale-while-revalidate` and `ETag` headers we implemented).
2.  **Telemetry Optimization:** Ensure the CDN allows query strings for the `/slice/` path to handle the `count` parameter.

### Step 4: Testing & Side-by-Side Validation
1.  **Verification:** Access the app via the new Static IP (using host header override) to ensure it loads from the CDN.
2.  **Side-by-Side:** The current Ingress (`origin.airsports.no`) will continue to serve absolute GCS URLs, while the new Gateway handles everything via relative paths.

### Step 5: Traffic Cutover
1.  **DNS Update:** Change the A record for `airsports.no` to point to the new Load Balancer IP.
2.  **Environment Variables:** Once testing is complete, update GKE environment variables to use relative paths for maximum efficiency:
    *   `STATIC_URL_BASE=/static/`
    *   `MEDIA_URL_BASE=/media/`

---

## 4. Advantages of this Approach
*   **Infinite Scalability:** Telemetry and Dashboard lists are served from the edge.
*   **Security:** `CDNSafetyMiddleware` protects private data.
*   **UX:** Astro provides a sub-second initial landing experience, while the React app handles complex logic seamlessly behind the proxy.
