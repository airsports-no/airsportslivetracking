# GKE Autopilot Prewarming for High-Usage Days

This directory contains scripts to prepare the Air Sports Live Tracking (ASLT) cluster for days with high concurrent scoring activity (e.g., major competitions).

## Why is this needed?
Calculator jobs in ASLT are created on-demand as Kubernetes Jobs. In GKE Autopilot, this can lead to "cold start" delays of 1-2 minutes while new nodes are provisioned for each wave of contestants. 

By using "Pause Pods," we force GKE to provision nodes in advance. These pods have a lower priority than real calculator jobs, so they will be immediately preempted when a real job needs the resources.

## Usage

### 1. Prewarm the Cluster
Run this script 30-60 minutes before the competition starts.

```bash
# Prewarm with 50 buffer slots (default)
./prewarm.sh

# Prewarm with a specific number of slots (e.g., 100)
./prewarm.sh 100
```

This script:
1. Creates a `low-priority-pause` PriorityClass.
2. Deploys `gke-prewarm-buffer` (Pause pods) with resources matching `calculator-job`.
3. Scales the core services HPAs (`web`, `celery`, `daphne`) to `minReplicas: 10`.

### 2. Teardown (Post-Competition)
Run this script after the day's flights are finished to avoid unnecessary costs.

```bash
./teardown.sh
```

This script:
1. Deletes the `gke-prewarm-buffer` deployment.
2. Resets HPA `minReplicas` to `2`.

## Monitoring
You can monitor the status of the buffer pods with:
```bash
kubectl get pods -l app=prewarm-buffer
```
And node count with:
```bash
kubectl get nodes
```
