from rest_framework import serializers
from api.models import RiderVehicleDetails

class RiderVehicleDetailsSerializer(serializers.ModelSerializer):

    type = serializers.CharField(source='v_type', required=True)
    brand = serializers.CharField(source='v_brand', required=True)
    model = serializers.CharField(source='v_model', required=True)
    color = serializers.CharField(source='v_color', required=True)
    plate_number = serializers.CharField(source='v_plate_number', required=True)
    or_cr_img = serializers.FileField(source='v_or_cr_img', required=True)
    vehicle_img = serializers.FileField(source='v_vehicle_img', required=True)

    class Meta:
        model = RiderVehicleDetails
        fields = [
            "id",
            "rider_id",
            "type",
            "brand",
            "model",
            "color",
            "plate_number",
            "or_cr_img",
            "vehicle_img"
        ]
