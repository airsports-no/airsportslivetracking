#!/bin/bash

NAME="live_tracking_map"                           #Name of the application (*)
DJANGODIR=/src/                               # Django project directory (*)
NUM_WORKERS=2                                # how many worker processes should Gunicorn spawn (*)
NUM_THREADS=5                                 # How many threads should each worker have
DJANGO_SETTINGS_MODULE=live_tracking_map.settings  # which settings file should Django use (*)
DJANGO_WSGI_MODULE=live_tracking_map.wsgi          # WSGI module name (*)

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
# RUNDIR=$(dirname $SOCKFILE)
# test -d $RUNDIR || mkdir -p $RUNDIR

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec gunicorn \
  --name $NAME \
  --workers $NUM_WORKERS \
  --threads $NUM_THREADS \
  --timeout 30 \
  --bind=:8002 \
  --log-level debug \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --forwarded-allow-ips="*" \
  ${DJANGO_WSGI_MODULE}:application