from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.booking_payment_model import BookingPayment
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger

class BookingPaymentRepository:
    
    @staticmethod
    @transaction.atomic
    def create(booking_instance, booking_payment):
        new_booking_pament = BookingPayment.objects.create(
            booking=booking_instance,
            type=booking_payment.get("type", ""),
            minimum_fare=booking_payment.get("minimum_fare", ""),
            pesos_per_km=booking_payment.get("pesos_per_km", ""),
            booking_fee=booking_payment.get("booking_fee", ""),
            tip=booking_payment.get("tip", ""),
            total_amount=booking_payment.get("total_amount", ""),
        )

        new_booking_pament.save()
        return new_booking_pament
