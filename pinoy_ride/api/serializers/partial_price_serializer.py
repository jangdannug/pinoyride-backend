from rest_framework import serializers
from api.models import Price
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class PartialPriceSerializer(serializers.ModelSerializer):

    km_pretty = serializers.SerializerMethodField()
    time_travel_pretty = serializers.SerializerMethodField()

    class Meta:
        model = Price
        fields = [
            "id",
            "price",
            "km",
            "km_pretty",
            "time_travel",
            "time_travel_pretty",
            "exceed_time_travel_price",
            "status"
        ]


    def get_km_pretty(self, obj):
        if obj.km:
            km_unit = ' kmph'
            return str(obj.km) + km_unit
        return None

    
    def get_time_travel_pretty(self, obj):
        if obj.time_travel:
            time_travel_unit = ' Mins'
            return str(obj.time_travel) + time_travel_unit
        return None


