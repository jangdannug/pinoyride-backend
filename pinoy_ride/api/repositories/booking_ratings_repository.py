from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.booking_ratings_model import BookingRatings
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger

class BookingRatingsRepository:
    
    @staticmethod
    @transaction.atomic
    def create(booking_instance, booking_ratings):
        new_booking_ratings = BookingRatings.objects.create(
            booking=booking_instance,
            rate=booking_ratings.get("rate", ""),
            compliment=booking_ratings.get("compliment", ""),
        )

        new_booking_ratings.save()
        return new_booking_ratings