from rest_framework import serializers
from api.models import BookingPayment

class BookingPaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = BookingPayment
        fields = [
            "id",
            "type",
            "booking_id",
            "minimum_fare",
            "pesos_per_km",
            "booking_fee",
            "booking_fee",
            "promo_discount",
            "total_amount_wo_promo",
            "total_amount",
            "tip",
            "status"
        ]