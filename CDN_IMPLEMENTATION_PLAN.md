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

The application codebase is now fully CDN-ready.

### A. Telemetry Minute-Slicing & Chunking API
1.  **Purpose:** Provides **Historical Backfill** when a spectator joins an active or past flight.
2.  **Live Data:** All real-time telemetry is pushed via **WebSockets**; the REST API is not used for live updates.
3.  **Efficiency:** Supports **aligned 15-minute chunks** to reduce backfill origin requests by 15x.
4.  **Transition Window:** Backfill slices remain "live" (max-age=5) until 120s after their end time. This handles late-arriving data for ongoing flights.
5.  **Immutability:** Once a slice is older than 120s, it is marked "immutable" (max-age=1yr), ensuring spectators can backfill history almost entirely from the CDN.

### B. Dashboard Versioning & ETag Strategy
1.  **Clean URLs:** Removed `?v=` hashes in favor of stable URLs with ETag validation.
2.  **Performance:** Integrated `stale-while-revalidate=86400` for public lists to prevent cache stampedes during version bumps.
3.  **Request Coalescing:** Cloud CDN's request collapsing ensures only one request hits the origin for a specific miss.

### C. CDN Safety Middleware
1.  **Security:** Forces `Vary: Authorization, Cookie` on all API responses.
2.  **Protection:** Defaults all non-public API endpoints to `private, no-cache`.
3.  **Error Integrity:** Explicitly sets `no-store` on 401, 403, and 400 responses to prevent auth leaks or negative caching.

---

## 3. Infrastructure Implementation Guide (Phase 1 & 3) 🚀

### Step 1: Configure Load Balancer Frontends
1.  Reserve a **Global Static IP** (Regional IPs are incompatible with Global HTTPS LBs).
2.  Create Managed SSL certificates for `airsports.no` and `app.airsports.no`.
3.  **Force HTTPS:** Configure the Load Balancer to redirect all HTTP traffic to HTTPS to prevent duplicate cache entries.

### Step 2: Set Up Backend Buckets & Origins
1.  **Static-Bucket:** Point to `airsports-static` GCS (Mode: `FORCE_CACHE_ALL`). Ensure static JS/CSS bundles are included.
2.  **Media-Bucket:** Point to `airsports-data` GCS (Mode: `FORCE_CACHE_ALL`).
3.  **Astro-Origin:** Create Internet NEG for the Firebase Hosting domain.
4.  **GKE-Origin:** Point to the existing GKE NEG (Mode: `USE_ORIGIN_HEADERS`).

### Step 3: Kubernetes Configuration (Order Matters)
1.  **BackendConfig:** Apply the `BackendConfig` CRD *before* annotating the Service.
2.  **NEG Activation:** Ensure the Service is annotated with `cloud.google.com/neg: '{"ingress": true}'` for container-native load balancing.
3.  **Verification:** Run `kubectl get backendconfig` and `kubectl get svc <name> -o jsonpath='{.metadata.annotations}'` before proceeding.

### Step 4: Testing & Shadow Phase
1.  **Shadow IP:** Use a separate IP for initial testing.
2.  **HTTP-only Test:** Recommend starting with HTTP-only for the shadow test to focus on header behavior and cache hits without certificate provisioning delays.
3.  **Validation Check:**
    - `curl -I http://<ip>/api/v1/contestant/X/slice/0/` should return `Age:` and `X-Cache-Lookup: HIT`.
    - "Live" slices must show `max-age=5`.
    - "Finished" slices must show `max-age=31536000, immutable`.

---

## 4. Operational Runbook 🛠️

### Emergency Cache Invalidation
If stale or corrupted data is poisoned in the CDN, use the following command to purge all caches:
```bash
gcloud compute url-maps invalidate-cdn-cache <url-map-name> --path "/*"
```
Note: Invalidation can take several minutes to propagate globally.

### Scaling Considerations
If initial flight loading (9000+ slice requests for long flights) saturates clients, consider increasing the chunk `count` in the frontend fetch logic from 15 to 30 or 60.
