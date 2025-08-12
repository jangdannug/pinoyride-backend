from rest_framework import serializers
from api.models import Price
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class PriceSerializer(serializers.ModelSerializer):

    price = serializers.IntegerField(required=True)
    km = serializers.IntegerField(required=True)
    time_travel = serializers.IntegerField(required=True)
    exceed_time_travel_price = serializers.IntegerField(required=True)
    status = serializers.CharField(required=False)

    class Meta:
        model = Price
        fields = [
            "id",
            "price",
            "km",
            "time_travel",
            "exceed_time_travel_price",
            "status"
        ]