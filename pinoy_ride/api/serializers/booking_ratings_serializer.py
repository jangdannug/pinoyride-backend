from rest_framework import serializers
from api.models import BookingRatings

class BookingRatingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = BookingRatings
        fields = [
            "id",
            "booking_id",
            "rate",
            "compliment"
        ]