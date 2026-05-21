#!/bin/bash

# Default number of pods to prewarm if not specified
BUFFER_PODS=${1:-50}

echo "🚀 Starting prewarm for high usage day ($BUFFER_PODS pods)..."

# 1. Create the Low-Priority Class if it doesn't exist
# Priority -10 is below default (0), so these pods are always preempted by real work.
cat <<EOF | kubectl apply -f -
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: low-priority-pause
value: -10
globalDefault: false
description: "Low priority class for pause pods to over-provision capacity."
EOF

# 2. Deploy the Pause Pods
# Using the same resources and nodeSelector as the calculator jobs
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gke-prewarm-buffer
spec:
  replicas: $BUFFER_PODS
  selector:
    matchLabels:
      app: prewarm-buffer
  template:
    metadata:
      labels:
        app: prewarm-buffer
    spec:
      priorityClassName: low-priority-pause
      nodeSelector:
        cloud.google.com/compute-class: Balanced
      containers:
      - name: pause
        image: registry.k8s.io/pause:3.9
        resources:
          requests:
            cpu: 400m
            memory: 500Mi
EOF

# 3. Pre-scale the core services HPAs
# This forces GKE to spin up pods and nodes for web/celery/daphne immediately
echo "📈 Scaling up HPA minReplicas for core services..."
kubectl patch hpa hpa-tracker-web --patch '{"spec": {"minReplicas": 10}}'
kubectl patch hpa hpa-tracker-celery --patch '{"spec": {"minReplicas": 3}}'
kubectl patch hpa hpa-tracker-daphne --patch '{"spec": {"minReplicas": 10}}'

echo "✅ Prewarm initiated. GKE Autopilot will now provision nodes to accommodate the buffer."
echo "Check progress with: kubectl get pods -l app=prewarm-buffer"
