#!/bin/bash

NAME="live_tracking_map"                           #Name of the application (*)
DJANGODIR=/src/                               # Django project directory (*)
NUM_WORKERS=5                                # how many worker processes should Gunicorn spawn (*)
NUM_THREADS=2                                 # How many threads should each worker have
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

# Start your Django Unicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
exec daphne -b 0.0.0.0 -p 8003 ${DJANGO_WSGI_MODULE}:application
