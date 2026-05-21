#!/bin/bash

echo "📉 Tearing down prewarm buffer and returning to normal state..."

# 1. Remove the buffer deployment
kubectl delete deployment gke-prewarm-buffer --ignore-not-found=true

# 2. Reset HPA minReplicas to default values (2 as per Helm charts)
echo "🔄 Resetting HPA minReplicas to defaults..."
kubectl patch hpa hpa-tracker-web --patch '{"spec": {"minReplicas": 2}}'
kubectl patch hpa hpa-tracker-celery --patch '{"spec": {"minReplicas": 2}}'
kubectl patch hpa hpa-tracker-daphne --patch '{"spec": {"minReplicas": 2}}'

# 3. Optional: Remove the PriorityClass
# We can keep it for future use, but if you want it gone:
# kubectl delete priorityclass low-priority-pause

echo "✅ Teardown complete. Autopilot will automatically scale down nodes as pods are removed."
echo "Note: Scale down may take 10-15 minutes depending on GKE Autopilot's internal cooling-off periods."
