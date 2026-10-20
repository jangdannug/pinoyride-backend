import os

from django.conf import settings

from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pinoy_ride.settings')

app = Celery('pinoy_ride')


app.config_from_object('pinoy_ride.settings', namespace='CELERY')


app.autodiscover_tasks()

app.conf.beat_schedule = {
    **(app.conf.beat_schedule or {}),
    "remind-advance-bookings": {"task": "api.tasks.remind_advance", "schedule": 60.0},
    "flag-at-risk-advance-bookings": {"task": "api.tasks.flag_at_risk_advance", "schedule": 60.0},
}
