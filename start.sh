#!/bin/bash
python3 pinoy_ride/manage.py migrate
gunicorn pinoy_ride.pinoy_ride.wsgi --bind 0.0.0.0:$PORT
