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
            promo_discount=booking_payment.get("promo_discount", ""),
            total_amount_wo_promo=booking_payment.get("total_amount_wo_promo", ""),
            total_amount=booking_payment.get("total_amount", ""),
            base_amount=booking_payment.get("base_amount", ""),
            distance_km_round=booking_payment.get("distance_km_round", ""),
            all_payment_details=booking_payment.get("all_payment_details", {}),
        )

        new_booking_pament.save()
        return new_booking_pament


    ## Add tip
    @transaction.atomic
    def add_tip(self, booking_payment_instance, tip):
        """Add tip"""
        tip = float(tip)
        minimum_fare = booking_payment_instance.minimum_fare
        base_amount = booking_payment_instance.base_amount
        booking_fee = booking_payment_instance.booking_fee
        total_amount = minimum_fare + base_amount + booking_fee + tip
        
        # Compute commission and rider net amount
        commission_prcentage = .15 #15%
        commission = round(total_amount * commission_prcentage, 2)
        rider_net_amount = round(total_amount - commission, 2)

        booking_payment_instance.commission = commission
        booking_payment_instance.rider_net_amount = rider_net_amount
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
