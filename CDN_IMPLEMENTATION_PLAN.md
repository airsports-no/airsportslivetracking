# CDN High-Load & Universal Entry Point Implementation Plan

This document tracks the migration of mission-critical telemetry to be served via Google Cloud CDN, plus the matching split of the public site into a marketing front-page and a dedicated application sub-domain.

> **Status (2026-04-27):**
> - Phase 1 (Marketing Integration) ✅ **Done**. Marketing site is now served via Django on `airsports.no`.
> - Phase 2 (Application code) ✅ **Done**.
> - Phase 3 (Infra) ⚠️ **In Progress** — Gateway API hostnames updated; CDN activation pending "Backend Bucket" config for assets.

---

## 1. Universal Entry Point Strategy (Integrated Hybrid)

**Decision (2026-04-27):** Instead of a hard split between Firebase and GKE, we have integrated the Astro marketing site into the main application container. This allows us to maintain backwards compatibility for the API on the root domain while moving the primary app experience to a subdomain.

### Domain Map
| Domain | Content | Logic |
| :--- | :--- | :--- |
| `airsports.no` | **Marketing Site** | Served via `CombinedFrontEndView` (Astro `dist` on disk) |
| `airsports.no/api/` | **Legacy API** | Routed to Django API (Backwards Compatibility) |
| `app.airsports.no` | **Main Application** | Routed to React SPA |

### Implementation Details
- **`CombinedFrontEndView`**: Uses the `Host` header to decide whether to serve static HTML from `/marketing_dist` (Astro) or the React template.
- **`STATICFILES_DIRS`**: Includes `/marketing_dist` so assets are collected and uploaded to GCS during deployment.
- **Headers**: `USE_X_FORWARDED_HOST` enabled to ensure Django correctly identifies the domain behind the Global Load Balancer.

---

## 2. Completed Application Optimizations ✅
*(Sections A-D remain valid from previous plan...)*

---

## 3. Infrastructure (Phase 3) — The "Last Mile" 🚀

### A. Completed (2026-04-27)
- **Hostnames**: `app.airsports.no` added to Gateway API `HTTPRoute` and GKE Managed Certificates.
- **Dockerfile**: Multi-stage build now includes Astro compilation.
- **Routing**: Catch-all `CombinedFrontEndView` handles pretty URLs for the marketing site.

### B. CRITICAL TODO: Asset Performance Optimization ⚠️

1.  **Switch to Relative Static URL**: ✅ **Done in code.**
    - Both `react_vite/vite.config.js` and `airsports_static/astro.config.mjs` are now configured to use `base: '/static/'` in production.
2.  **Add Backend Bucket to HTTPRoute**: 🔴 **Still Needed.**
    - Update `helm/templates/httproute_root.yaml` to include a rule for `/static/*`.
    - Point this rule to a `BackendBucket` referencing the `airsports-static` GCS bucket.
    - This enables **Global Edge Caching** for JS/CSS and **HTTP/2 Multiplexing** (single connection for HTML and assets).

### C. TODO: Verify HTML Caching 🔍
Once the GKE Gateway bug is resolved:
- Ensure `airsports.no` (the marketing HTML) is being cached by the CDN.
- **Test:** `curl -sI https://airsports.no/` should show `X-Cache-Lookup: HIT` on the second request.
- **Verification:** Since Django is serving these files from a local disk (`/marketing_dist`), the response time is fast, but CDN caching is required to handle high traffic.

---

## 4. Operational Runbook 🛠️

### Emergency cache invalidation
```bash
gcloud compute url-maps invalidate-cdn-cache <url-map-name> --path "/*"
```

### Adding new Marketing Pages
Simply add the `.astro` file to `airsports_static/src/pages/`. The `CombinedFrontEndView` is designed to automatically find and serve the resulting `.html` file from `/marketing_dist` without further code changes.
