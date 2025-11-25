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
            "base_amount",
            "total_amount",
            "tip",
            "status"
        ]