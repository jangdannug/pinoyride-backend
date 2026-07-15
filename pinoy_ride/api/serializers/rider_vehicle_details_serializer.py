from rest_framework import serializers
from api.models import RiderVehicleDetails
import os

class RiderVehicleDetailsSerializer(serializers.ModelSerializer):

    type = serializers.CharField(source='v_type', required=True)
    brand = serializers.CharField(source='v_brand', required=True)
    model = serializers.CharField(source='v_model', required=True)
    color = serializers.CharField(source='v_color', required=True)
    plate_number = serializers.CharField(source='v_plate_number', required=True)
    or_cr_img = serializers.FileField(source='v_or_cr_img', required=True)
    vehicle_img = serializers.FileField(source='v_vehicle_img', required=True)
    or_cr_img_pretty = serializers.SerializerMethodField()
    vehicle_img_pretty = serializers.SerializerMethodField()

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
            "vehicle_img",
            "or_cr_img_pretty",
            "vehicle_img_pretty"
        ]

    def get_or_cr_img_pretty(self, obj):
        """Return full URL for OR/CR image"""
        if obj.v_or_cr_img and hasattr(obj.v_or_cr_img, 'name'):
            base_url = os.getenv('IMAGE_BASE_URL', 'http://127.0.0.1:7966/media')
            return f"{base_url}/{obj.v_or_cr_img.name}"
        return None

    def get_vehicle_img_pretty(self, obj):
        """Return full URL for vehicle image"""
        if obj.v_vehicle_img and hasattr(obj.v_vehicle_img, 'name'):
            base_url = os.getenv('IMAGE_BASE_URL', 'http://127.0.0.1:7966/media')
            return f"{base_url}/{obj.v_vehicle_img.name}"
        return None
