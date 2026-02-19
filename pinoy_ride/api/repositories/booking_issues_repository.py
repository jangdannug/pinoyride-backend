from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.booking_issues_model import BookingIssues
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger

class BookingIssuesRepository:
    
    @staticmethod
    @transaction.atomic
    def create(booking_instance, booking_issues):
        new_booking_issues = BookingIssues.objects.create(
            booking=booking_instance,
            issue_txt=booking_issues.get("issue", ""),
            user_type=booking_issues.get("user_type", ""),
            reported_by=booking_issues.get("reported_by", ""),
        )

        new_booking_issues.save()
        return new_booking_issues