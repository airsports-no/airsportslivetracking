#!/bin/bash

# Combined HTTP + websocket app server. Replaces the previous split of
# gunicorn.sh (WSGI, HTTP only) and daphne.sh (ASGI, websockets only) running
# as two separate deployments - live_tracking_map.asgi already routes both
# protocols via ProtocolTypeRouter, so one process serves everything.

NAME="live_tracking_map"                           #Name of the application (*)
DJANGODIR=/src/                               # Django project directory (*)
NUM_WORKERS=${NUM_WORKERS:-1}
TIMEOUT=${GUNICORN_TIMEOUT:-120}
GRACEFUL_TIMEOUT=${GUNICORN_GRACEFUL_TIMEOUT:-45}
# Must exceed the GCP load balancer's 600s backend idle timeout, otherwise the
# backend closes first and the LB serves intermittent 502s.
KEEP_ALIVE=${GUNICORN_KEEP_ALIVE:-620}

DJANGO_SETTINGS_MODULE=live_tracking_map.settings  # which settings file should Django use (*)
DJANGO_ASGI_MODULE=live_tracking_map.asgi          # ASGI module name (*)

echo "Starting $NAME as `whoami`"

cd $DJANGODIR
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Notes on the flags:
#   --workers defaults to 1 and we scale out with replicas instead. Each worker
#     is a full Django interpreter, so extra workers multiply the memory
#     request - the opposite of what we want at idle.
#   --timeout is NOT a request timeout for an ASGI worker. Gunicorn only kills
#     the worker when uvicorn stops emitting its heartbeat, i.e. when the event
#     loop itself is blocked - a slow view in a thread never trips it. Request
#     duration is bounded by the GCP LB backend timeout instead. Keep this
#     generous: a false arbiter kill drops every live websocket on the pod.
#   No --max-requests: uvicorn counts each websocket connection as a request,
#     so recycling would fire on connects and drop tracking sessions. Worker
#     recycling is handled by the per-commit rollout instead (image.tag is the
#     commit SHA, so every deploy replaces all pods).
#   No --threads: it does nothing for an ASGI worker - gunicorn's thread
#     setting is ignored by the uvicorn worker class entirely.
#   --forwarded-allow-ips replaces daphne's --proxy-headers, so
#     SECURE_PROXY_SSL_HEADER and client IPs stay correct behind the GCP LB.
exec gunicorn \
  --name $NAME \
  -k live_tracking_map.uvicorn_worker.ASLTUvicornWorker \
  --workers $NUM_WORKERS \
  --timeout $TIMEOUT \
  --graceful-timeout $GRACEFUL_TIMEOUT \
  --keep-alive $KEEP_ALIVE \
  --bind=:8002 \
  --log-level warning \
  --forwarded-allow-ips="*" \
  ${DJANGO_ASGI_MODULE}:application
