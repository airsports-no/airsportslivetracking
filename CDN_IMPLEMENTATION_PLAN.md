# CDN High-Load Implementation Plan

This document outlines the technical steps required to migrate the **Mission Dashboard** and **Competition Map** telemetry to be served via Google Cloud CDN using standard HTTP caching directives.

---

## 1. Core Architecture Principles
*   **Immutability:** Convert dynamic requests into static requests using deterministic URL patterns.
*   **Origin Control:** Django (Origin) defines caching behavior via `Cache-Control` headers.
*   **Deterministic URLs:** Ensure that query parameters (filters, versions, user IDs) are part of the URL to create unique cache keys at the CDN edge.

---

## 2. Backend Changes (Django/DRF)

### A. Telemetry Minute-Slicing API (Per-Contestant)
**File:** `src/display/viewsets.py` & `src/display/urls_api.py`
1.  **New Endpoint:** `/api/v1/contestant/<contestant_id>/slice/<minute_index>/`
2.  **Logic:**
    *   Fetch `Contestant.takeoff_time`.
    *   Calculate `start_window = takeoff_time + (minute_index * 60s)`.
    *   Calculate `end_window = start_window + 60s`.
    *   Filter `TrackPosition` for this specific `contestant_id` where `time >= start_window` and `time < end_window`.
3.  **Header Logic (Origin Side):**
    *   **Finished Slices:** If `end_window < now()` AND (Contestant is finished OR `end_window < now() - 120s`):
        *   Set `Cache-Control: public, max-age=31536000, immutable`.
    *   **Live Slices:** If this is the "current" or "future" slice for an active flight:
        *   Set `Cache-Control: public, max-age=5, must-revalidate`.

### B. Mission Dashboard Versioning
**File:** `src/display/viewsets.py` (`ContestViewSet.list`)
1.  **Deterministic Cache Keys:**
    *   Modify the `list` method to respect a `v` (version) and `u` (user_id) query parameter.
    *   The backend must verify that the `u` parameter matches `request.user.id` (if authenticated).
2.  **Header Logic:**
    *   If `v` is present in the URL:
        *   Set `Cache-Control: public, max-age=3600`. (When data changes, `v` bumps, creating a new URL and a new CDN cache entry).
    *   The existing manual Redis cache remains as a second layer of protection for "Cache Misses" at the CDN.

---

## 3. Frontend Changes (React/Vite)

### A. Competition Map Telemetry Stitching
**File:** `react_vite/src/features/competition-map/hooks/useCompetitionData.ts`
1.  **Contestant Tracking State:**
    *   Maintain a `Map<contestantId, Map<minuteIndex, TrackPosition[]>>` to store chunks.
2.  **Initial Load:**
    *   For each contestant, compare `takeoff_time` to `now`.
    *   Calculate the required `max_index`.
    *   Fetch all indices from 0 to `max_index` in parallel (limited by browser concurrency).
3.  **Real-time Polling:**
    *   Instead of one global timer, the hook calculates the "current index" for each contestant based on their `takeoff_time`.
    *   Every 10-15 seconds, it requests the latest index for all non-finished contestants.
    *   When an index "rolls over," the previous index is fetched one last time to ensure the full 60s of data is captured and cached.

### B. Dashboard Version Injection
**File:** `react_vite/src/features/mission-dashboard/store.ts`
1.  Update `fetchContests` to always include the `v` parameter from `document.configuration.contest_list_version`.
2.  Include the `u` parameter (authenticated user ID) to ensure the CDN caches the list correctly for the specific user's permissions (`is_editor`, etc.).

---

## 4. Google Cloud Infrastructure Path

### A. GKE Configuration
1.  **BackendConfig:** Create a Kubernetes `BackendConfig` resource.
    ```yaml
    apiVersion: cloud.google.com/v1
    kind: BackendConfig
    metadata:
      name: cdn-backend-config
    spec:
      cdn:
        enabled: true
        cachePolicy:
          includeHost: true
          includeProtocol: true
          includeQueryString: true  # CRITICAL for filters and ?v=
    ```
2.  **Service Annotation:** Annotate the Django Service to use this `BackendConfig`.

### B. Shadow Testing Environment (The "New IP" Approach)
To test without affecting the primary site:
1.  **Static IP:** Reserve a Global Static IP `cdn-test-ip`.
2.  **Load Balancer:** Create a new Global External HTTP(S) Load Balancer (Classic or Standard).
    *   **Frontend:** Point to `cdn-test-ip`.
    *   **Backend:** Point to the existing GKE Network Endpoint Group (NEG).
    *   **CDN:** Enable on this specific backend.
3.  **Frontend Toggle:** Add a `?useCdn=true` flag to the app. When active, it changes the `API_BASE_URL` to point to the new IP/domain.

---

## 5. Verification & Migration Steps
1.  **Step 1:** Implement Backend Slicing and Header Logic.
2.  **Step 2:** Deploy the "Shadow" Load Balancer with CDN enabled.
3.  **Step 3:** Update Frontend to support the `?useCdn=true` mode and verify telemetry stitching.
4.  **Step 4:** Load test the `cdn-test-ip` using `k6` or `locust`. Observe that GKE CPU usage remains low while CDN "Cache Hit" rate is high.
5.  **Step 5:** Final cutover: Point the main production domain to the CDN-enabled Load Balancer frontend.
