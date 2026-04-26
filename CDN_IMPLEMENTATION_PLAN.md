# CDN High-Load & Universal Entry Point Implementation Plan

This document tracks the migration of mission-critical telemetry to be served via Google Cloud CDN, plus the matching split of the public site into a marketing front-page and a dedicated application sub-domain.

> **Status (2026-04-25 evening):**
> - Phase 2 (application code) ✅ done.
> - Phase 3 (infra) **in progress** — global premium IP and GKE Gateway provisioned tonight; CDN activation blocked by an upstream gateway-controller bug. Browser-side ETag/Cache-Control delivers partial origin relief in the meantime.

---

## 1. Universal Entry Point Strategy (Two Domains, No Proxy)

**Decision (2026-04-25):** The earlier hybrid plan (proxy `/api/*`, `/admin/*`, etc. from `airsports.no` to GKE) is **abandoned**. The simpler, cleaner split below has been adopted instead.

### Domain Map
| Domain | Content | Hosting |
| :--- | :--- | :--- |
| `airsports.no` | Astro marketing site only | Firebase Hosting (CDN-fronted via the same LB as `app`) |
| `app.airsports.no` | Full application **including the API** (`/api/*`, `/admin/*`, dashboards, …) | Google Cloud LB + CDN → GKE |

### What this removes from earlier plan
- No path-based routing rules on `airsports.no` to forward `/api/*`, `/admin/*`, `/accounts/*`, `/display/*`, etc. to GKE
- No risk of marketing-site cache poisoning from authenticated traffic
- No need to keep `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` symmetric across both hosts for application paths

### API consumer migration
The API endpoint moves from `https://airsports.no/api/*` to `https://app.airsports.no/api/*`. Few external integrators exist; they will be **contacted directly** with a cutover date. No general 301-redirect compatibility layer.

> **TODO before cutover:** identify and notify the active API integrators. Keep a short list in this repo (or in Linear) so the cutover date is visible.

---

## 2. Completed Application Optimizations (Phase 2) ✅

### A. Telemetry Minute-Slicing & Chunking API
- **Endpoint:** `/api/v1/contestant/<id>/slice/<minute_index>/?count=<n>`
- **Purpose:** Historical backfill when a spectator joins an active or past flight. Live telemetry is pushed via WebSockets; this REST endpoint is **not** used for real-time updates.
- **Aligned 15-minute chunks** reduce backfill origin requests by 15× when the frontend asks for `count=15`.
- **Live window:** until 120s past `end_window`, the slice returns `Cache-Control: public, max-age=5, must-revalidate` (only when the navigation task and contest are both `is_public`; otherwise `private, no-cache`).
- **Finished window:** `Cache-Control: public, max-age=60, s-maxage=31536000, stale-while-revalidate=86400`.
- **ETag short-circuit only on finished slices.** `track_version` only bumps on calculator (re)start, not on each position append, so a live ETag match would incorrectly 304 even when new positions had arrived. Finished windows are immutable, so 304 is safe there.
- **`count` capped to `[1, 60]`** to bound the per-request DB scan.

### B. Dashboard Versioning & ETag Strategy
- Clean URLs (no `?v=` hash) with ETag-based revalidation.
- `stale-while-revalidate=86400` on public lists prevents cache stampedes when content changes.
- Cloud CDN request collapsing keeps origin pressure low on misses.

### C. CDN Safety Middleware (`live_tracking_map.middleware.CDNSafetyMiddleware`)
- Registered **first** in `MIDDLEWARE` so it sees the response *last* and can override `Vary` added by other middlewares (especially `SessionMiddleware`).
- Defaults all `/api/*` responses to `Cache-Control: private, no-cache` if the view didn't set one.
- Forces `no-store` on 400/401/403 responses so auth failures are never negative-cached.
- For non-public responses: adds `Vary: Authorization, Cookie` so the CDN can't serve one user's response to another.
- For `Cache-Control: public` responses: **strips** `Cookie` and `Authorization` from `Vary`, even if other middleware added them. Without this, a `Vary: Cookie` on a public endpoint would fragment the CDN cache per-user and reduce hit rate to ~0%.

### D. Tests
`src/display/tests/test_cdn_cache_headers.py` covers:
- Public slice → `Cache-Control: public`, no `Vary: Cookie`
- Private slice → `Cache-Control: private`, with `Vary: Cookie`
- Live slice → no premature 304 even with matching ETag
- Finished slice → 304 on matching ETag
- `count=120` → 400 with `Cache-Control: no-store`

---

## 3. Infrastructure (Phase 3) — In Progress 🚀

### A. Provisioned (2026-04-25 evening session)
- **Global premium-tier static IP** reserved.
- **GKE Gateway resource** deployed via `helm/one_shot_templates/gateway.yaml`.
- **GCPHTTPFilter** for CDN config: `helm/templates/gcp_http_filter.yaml` (intends to enable CDN on routes).
- **HTTPRoutes** updated to attach to the new gateway:
  - `helm/templates/httproute_root.yaml`
  - `helm/templates/httproute_mbtiles.yaml`
  - `helm/templates/httproute_traccar.yaml`
  - `helm/templates/httproute_traccarclient.yaml`

### B. Blocker — Gateway controller bug
The gateway controller is **not actually enabling CDN** on the underlying backend service, despite the policy/filter being applied. Symptom: responses lack `Age` / `X-Cache-Lookup` headers and origin sees full traffic.

**Verification one-liner once we want to recheck:**
```bash
gcloud compute backend-services list --global --format="table(name,enableCDN)"
```
If `enableCDN` is `False` on the gateway-managed backends despite the filter being applied, this is the bug.

**Action:** Wait on upstream fix from Google. No workaround applied; the partial gain from browser-side ETag/Cache-Control is acceptable as a stopgap.

### C. Partial gain available right now
Even with CDN inactive, the Phase 2 headers reduce load via:
- **Browser cache:** `max-age=5` (live) and `max-age=60, immutable` (finished) suppress repeat fetches client-side.
- **ETag 304s:** Conditional GETs save bandwidth on misses (origin still hit, but smaller responses).
- **`stale-while-revalidate`:** Background refresh hides revalidation latency from users.

This won't reduce origin CPU like CDN would, but it does cut bandwidth and improve perceived latency.

### D. Remaining infra steps once gateway bug is fixed
1. **DNS:** Point `app.airsports.no` A record to the global static IP. Keep `airsports.no` on Firebase Hosting for the marketing site.
2. **Managed SSL certs** for both `app.airsports.no` and `airsports.no`.
3. **Force HTTPS** on the LB (avoid duplicate cache entries between HTTP and HTTPS).
4. **GCS backend buckets** for `/static/*` and `/media/*` (mode `FORCE_CACHE_ALL`).
5. **Verification:**
   - `curl -sI https://app.airsports.no/api/v1/contestant/<id>/slice/0/` shows `Age:` and `X-Cache-Lookup: HIT` on second request.
   - Live slice: `Cache-Control: public, max-age=5, must-revalidate`.
   - Finished slice: `Cache-Control: ..., max-age=31536000, ..., stale-while-revalidate=86400`.
   - No `Vary: Cookie` on public responses.
6. **API consumer notification** — send the migration notice with cutover date.

---

## 4. Operational Runbook 🛠️

### Emergency cache invalidation
```bash
gcloud compute url-maps invalidate-cdn-cache <url-map-name> --path "/*"
```
Propagation takes several minutes globally.

### Scaling consideration
If initial flight loading (long flight × many contestants) saturates browser concurrency, raise the chunk `count` in the frontend fetcher from 15 toward 30 (max 60).

### Debugging "is CDN actually on?"
```bash
gcloud compute backend-services list --global --format="table(name,enableCDN)"
gcloud compute backend-services describe <name> --global | grep -A 5 cdnPolicy
```
