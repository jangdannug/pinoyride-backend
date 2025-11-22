from rest_framework import serializers
from api.models import Promo
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class PartialPromoSerializer(serializers.ModelSerializer):

    start_date_pretty = serializers.SerializerMethodField()
    end_date_pretty = serializers.SerializerMethodField()

    class Meta:
        model = Promo
        fields = [
            "id",
            "code",
            "name",
            "start_date_pretty",
            "end_date_pretty",
            "start_date",
            "end_date",
            "location",
            "no_of_users",
            "status"
        ]


    def get_start_date_pretty(self, obj):
        if obj.start_date:
            return obj.start_date.strftime("%B %d, %Y")
        return None


    def get_end_date_pretty(self, obj):
        if obj.end_date:
            return obj.end_date.strftime("%B %d, %Y") 
        return None


