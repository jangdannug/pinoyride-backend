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
            rider_net_amount=booking_payment.get("rider_net_amount", ""),
            commission=booking_payment.get("commission", ""),
            total_amount=booking_payment.get("total_amount", ""),
            base_amount=booking_payment.get("base_amount", ""),
            distance_km_round=booking_payment.get("distance_km_round", ""),
        )

        new_booking_pament.save()
        return new_booking_pament


    ## Add tip
    @transaction.atomic
    def add_tip(self, booking_payment_instance, tip):
        """Add tip"""
        tip = float(tip)
        minimum_fare = booking_payment_instance.minimum_fare
        pesos_per_km = booking_payment_instance.pesos_per_km
        booking_fee = booking_payment_instance.booking_fee
        total_amount = minimum_fare + pesos_per_km + booking_fee + tip
        
        booking_payment_instance.tip = tip
        booking_payment_instance.total_amount = round(total_amount, 2)
        booking_payment_instance.save()
        
        return booking_payment_instance
    
    @staticmethod
    def get_by_id(booking_id):
        """Get booking payment by booking id"""
        try:
            return BookingPayment.objects.get(booking_id=booking_id)
        except BookingPayment.DoesNotExist:
            return None
