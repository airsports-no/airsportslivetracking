#!/bin/bash

NAME="live_tracking_map"                           #Name of the application (*)
DJANGODIR=/src/                               # Django project directory (*)
DJANGO_SETTINGS_MODULE=live_tracking_map.settings  # which settings file should Django use (*)
DJANGO_ASGI_MODULE=live_tracking_map.asgi          # ASGI module name (*)

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
# RUNDIR=$(dirname $SOCKFILE)
# test -d $RUNDIR || mkdir -p $RUNDIR

# Start Daphne
exec daphne \
  -b 0.0.0.0 \
  -p 8003 \
  --proxy-headers \
  --websocket_timeout 3600 \
  --websocket_connect_timeout 60 \
  ${DJANGO_ASGI_MODULE}:application
