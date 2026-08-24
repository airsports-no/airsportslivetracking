# GKE Autopilot Prewarming for High-Usage Days

This directory contains scripts to prepare the Air Sports Live Tracking (ASLT) cluster for days with high concurrent scoring activity (e.g., major competitions).

## Why is this needed?
In GKE Autopilot, scaling up a Deployment can mean a "cold start" delay of 1-2 minutes while a
new node is provisioned. This directory's buffer covers that for `tracker-app`/`tracker-celery`
bursts.

The live-calculator pool (per-contestant scoring, `helm/templates/deployment_live_calculator.yaml`)
is a separate concern with its own answer: `src/calculator_pool_scaler.py` runs inside
`tracker-processor` and scales that Deployment ahead of each contestant's scheduled
`tracker_start_time` (see `CALCULATOR_POOL_PREWARM_MINUTES` in `helm/values.yaml`), so it is
already warm well before the node-provisioning window matters - no buffer pods needed there. For
an unusually large event, `kubectl scale deployment live-calculator --replicas=N` overrides the
scaler's own count by hand (the scaler will take it back over on its next poll, so re-run this if
you need it held past that).

By using "Pause Pods" for the tracker-app/tracker-celery case, we force GKE to provision nodes in
advance. These pods have a lower priority than real service pods, so they will be immediately
preempted when a real pod needs the resources.

## Usage

### 1. Prewarm the Cluster
Run this script 30-60 minutes before the competition starts.

```bash
# Prewarm with 50 buffer slots (default)
./prewarm.sh

# Prewarm with a specific number of slots (e.g., 100)
./prewarm.sh 100

# Also override the live-calculator pool's replica count (rarely needed -
# see "Why is this needed?" above; the scaler takes this back over on its
# next poll)
./prewarm.sh 100 8
```

This script:
1. Scales the `gke-prewarm-buffer` Deployment up to the requested pod count.
2. Raises the core service HPAs (`tracker-app`, `tracker-celery`) above their idle floors.

The `low-priority-pause` PriorityClass and a small standing `gke-prewarm-buffer`
(a couple of pods) are part of the Helm chart
(`helm/templates/prewarm_buffer.yaml`), so there is always a little preemptible
headroom even without running this. Note the buffer pods deliberately carry no
`compute-class` selector, so they reserve general-purpose capacity — the same
class `tracker-app` and the calculator jobs schedule onto.

### 2. Teardown (Post-Competition)
Run this script after the day's flights are finished to avoid unnecessary costs.

```bash
./teardown.sh
```

This script:
1. Scales `gke-prewarm-buffer` back to its standing size.
2. Resets HPA `minReplicas` to the chart defaults (`tracker-app` 2, `tracker-celery` 1).

## Monitoring
You can monitor the status of the buffer pods with:
```bash
kubectl get pods -l app=prewarm-buffer
```
And node count with:
```bash
kubectl get nodes
```
