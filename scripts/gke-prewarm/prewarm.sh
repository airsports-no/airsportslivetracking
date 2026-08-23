#!/bin/bash
set -euo pipefail

# Number of buffer pods to hold open during the event
BUFFER_PODS=${1:-50}

echo "🚀 Starting prewarm for high usage day ($BUFFER_PODS pods)..."

# The PriorityClass and the gke-prewarm-buffer Deployment are part of the Helm
# chart now (helm/templates/prewarm_buffer.yaml), which keeps a small standing
# buffer at all times. Prewarming just scales that same Deployment up for the
# event, rather than applying a competing copy of it - a `kubectl apply` here
# would be reverted by the next `helm upgrade`.
echo "📈 Scaling prewarm buffer to $BUFFER_PODS pods..."
kubectl scale deployment gke-prewarm-buffer --replicas="$BUFFER_PODS"

# Pre-scale the core services so their pods are already running when the
# first contestants connect.
echo "📈 Raising HPA minReplicas for core services..."
kubectl patch hpa hpa-tracker-app --patch '{"spec": {"minReplicas": 10}}'
kubectl patch hpa hpa-tracker-celery --patch '{"spec": {"minReplicas": 3}}'

echo "✅ Prewarm initiated. GKE Autopilot will now provision nodes to accommodate the buffer."
echo "Check progress with: kubectl get pods -l app=prewarm-buffer"
