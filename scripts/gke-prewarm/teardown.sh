#!/bin/bash
set -euo pipefail

echo "📉 Tearing down prewarm buffer and returning to normal state..."

# Scale the buffer back to the standing size the chart keeps at all times,
# rather than deleting it - the Deployment is Helm-managed now
# (helm/templates/prewarm_buffer.yaml), so deleting it would just be undone by
# the next `helm upgrade`.
BASELINE_BUFFER=${BASELINE_BUFFER:-2}
echo "🔄 Scaling prewarm buffer back to $BASELINE_BUFFER..."
kubectl scale deployment gke-prewarm-buffer --replicas="$BASELINE_BUFFER"

# Reset HPA minReplicas to the chart defaults. These must match
# helm/templates/hpa_tracker_app.yaml and hpa_tracker_celery.yaml - if you
# change them there, change them here.
echo "🔄 Resetting HPA minReplicas to chart defaults..."
kubectl patch hpa hpa-tracker-app --patch '{"spec": {"minReplicas": 2}}'
kubectl patch hpa hpa-tracker-celery --patch '{"spec": {"minReplicas": 1}}'

echo "✅ Teardown complete. Autopilot will automatically scale down nodes as pods are removed."
echo "Note: Scale down may take 10-15 minutes depending on GKE Autopilot's internal cooling-off periods."
