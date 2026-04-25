# CDN Shadow LB — Runbook

Step-by-step setup of a shadow Google Cloud Load Balancer with CDN enabled,
pointing at the **existing** GKE NEG for `tracker-web-service`. Prod is not
touched; the shadow LB just adds a second front door to the same backends.

> **HTTP-only tonight.** Skip TLS; flip to HTTPS later when there's energy
> for cert/DNS work.

---

## 0. Prerequisites — check first (5 min)

```bash
# Verify gcloud auth + project
gcloud config get-value project
gcloud config get-value compute/region

# If not already set:
export PROJECT_ID="airsports-production"        # confirm with: gcloud projects list
export REGION="europe-north1"
export CLUSTER="airsports-cluster"
gcloud config set project "$PROJECT_ID"

# Connect kubectl to the cluster
gcloud container clusters get-credentials "$CLUSTER" --region "$REGION"

# Verify the Django service exists
kubectl get svc tracker-web-service -n default
```

If `kubectl get svc` fails, fix the namespace first — everything below
assumes `default`.

---

## 1. Find the existing NEG (2 min)

The Ingress already created a NEG for `tracker-web-service`. Grab its name —
we'll attach the new backend service to it.

```bash
# List NEGs in the cluster's zones (europe-north1 has 3 zones)
gcloud compute network-endpoint-groups list \
  --filter="name~tracker-web-service" \
  --format="table(name,zone,size)"

# Expected: one NEG per zone (europe-north1-a, -b, -c).
# Note the names — typically: k8s1-<hash>-default-tracker-web-service-80-<hash>
```

Save the NEG names — used in step 5.

```bash
export NEG_NAME="<paste neg name from above, identical across zones>"
```

---

## 2. Reserve a global static IP (1 min)

```bash
gcloud compute addresses create cdn-test-ip --global

# Get the IP for later
export CDN_IP=$(gcloud compute addresses describe cdn-test-ip --global --format="value(address)")
echo "Shadow IP: $CDN_IP"
```

---

## 3. Create the BackendConfig CRD (3 min)

Save as `helm/templates/cdn_backend_config.yaml` so it's tracked in git.

```yaml
apiVersion: cloud.google.com/v1
kind: BackendConfig
metadata:
  name: cdn-backend-config
  namespace: default
spec:
  cdn:
    enabled: true
    cachePolicy:
      includeHost: true
      includeProtocol: true
      includeQueryString: true
    cacheMode: USE_ORIGIN_HEADERS  # honor Cache-Control from Django
    defaultTtl: 0                  # Django decides via headers
```

**NOTE:** This BackendConfig is for documentation / future use if you later
flip the existing Ingress to use CDN. For tonight's shadow LB we build the
backend service manually via `gcloud` (steps 4–7), which doesn't read
BackendConfig — we set CDN directly on the backend service.

Apply it anyway so it's ready:
```bash
kubectl apply -f helm/templates/cdn_backend_config.yaml
kubectl get backendconfig -n default
```

---

## 4. Create a health check (1 min)

```bash
gcloud compute health-checks create http cdn-test-hc \
  --port=80 \
  --request-path=/healthz \
  --check-interval=10s \
  --timeout=5s \
  --healthy-threshold=2 \
  --unhealthy-threshold=3
```

> Replace `/healthz` with whatever path Django returns 200 on without auth.
> If unsure: `curl -I https://airsports.no/` and use `/`.

---

## 5. Create the CDN-enabled backend service (2 min)

```bash
gcloud compute backend-services create cdn-test-backend \
  --global \
  --protocol=HTTP \
  --port-name=http \
  --health-checks=cdn-test-hc \
  --enable-cdn \
  --cache-mode=USE_ORIGIN_HEADERS \
  --cache-key-include-host \
  --cache-key-include-protocol \
  --cache-key-include-query-string \
  --connection-draining-timeout=60

# Attach the NEG (one command per zone)
for ZONE in europe-north1-a europe-north1-b europe-north1-c; do
  gcloud compute backend-services add-backend cdn-test-backend \
    --global \
    --network-endpoint-group="$NEG_NAME" \
    --network-endpoint-group-zone="$ZONE" \
    --balancing-mode=RATE \
    --max-rate-per-endpoint=100
done
```

> If a zone doesn't have endpoints (small cluster), skip it — `gcloud` will
> error and you continue.

---

## 6. URL map → HTTP proxy → forwarding rule (2 min)

```bash
# URL map: route everything to the backend
gcloud compute url-maps create cdn-test-urlmap \
  --default-service=cdn-test-backend

# HTTP target proxy
gcloud compute target-http-proxies create cdn-test-http-proxy \
  --url-map=cdn-test-urlmap

# Forwarding rule (binds IP:80 → proxy)
gcloud compute forwarding-rules create cdn-test-fw \
  --global \
  --target-http-proxy=cdn-test-http-proxy \
  --address=cdn-test-ip \
  --ports=80
```

---

## 7. Wait for LB to come up (5–10 min)

The LB takes a few minutes to propagate. Watch:

```bash
watch -n 10 "curl -sI http://$CDN_IP/ | head -10"
```

Initially you'll see `502` or connection refused. When it returns the same
HTML/headers as `airsports.no`, you're live.

---

## 8. Verify CDN behavior (5 min)

This is the win condition for tonight. All four should pass:

```bash
# 1. CDN is in front (look for Via, Age, X-Cache headers)
curl -sI "http://$CDN_IP/api/v1/contestant/<known_id>/slice/0/" \
  | grep -iE "cache-control|age|via|x-cache"

# 2. Second hit within 60s should show Age: > 0
sleep 5
curl -sI "http://$CDN_IP/api/v1/contestant/<known_id>/slice/0/" \
  | grep -iE "age|x-cache"

# 3. A "live" slice shows max-age=5
#    (pick a contestant currently flying, or just check current minute)

# 4. A "finished" slice shows max-age=31536000, immutable
#    (slice from a contestant who landed > 2 min ago)
```

If all four pass → infra side is done. Frontend toggle and cert work next session.

---

## 9. Cache invalidation (memorize this)

When you deploy and need to bust the cache:

```bash
gcloud compute url-maps invalidate-cdn-cache cdn-test-urlmap --path "/*"
```

For a specific path:
```bash
gcloud compute url-maps invalidate-cdn-cache cdn-test-urlmap \
  --path "/api/v1/contestant/123/slice/0/"
```

---

## 10. Teardown (when shadow is done or if you need to abort)

```bash
gcloud compute forwarding-rules delete cdn-test-fw --global -q
gcloud compute target-http-proxies delete cdn-test-http-proxy -q
gcloud compute url-maps delete cdn-test-urlmap -q
gcloud compute backend-services delete cdn-test-backend --global -q
gcloud compute health-checks delete cdn-test-hc -q
gcloud compute addresses delete cdn-test-ip --global -q
kubectl delete backendconfig cdn-backend-config -n default
```

---

## Risks & gotchas

- **Shadow load tests hit prod pods.** The shadow LB shares the NEG with
  the production Ingress — heavy `k6`/`locust` runs against `cdn-test-ip`
  will hit the same Django pods serving prod users. Limit concurrency.
- **Cookies bypass cache.** Cloud CDN refuses to cache responses with
  `Set-Cookie`. If telemetry endpoints return cookies (CSRF middleware?),
  cache-hit-rate will be 0%. Verify with `curl -sI` — if `Set-Cookie`
  appears on slice responses, strip it on those endpoints in Django.
- **Authenticated dashboard endpoints will not cache** unless you explicitly
  configure cookie handling. Park this for a later session — telemetry is
  the volume win, dashboard is secondary.
- **`Vary: Cookie` from Django** also kills caching. Check response headers
  on the slice endpoint and remove if present.
