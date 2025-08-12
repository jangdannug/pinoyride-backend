from rest_framework import serializers
from api.models import Rider
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class PartialRiderSerializer(serializers.ModelSerializer):

    vehicle_details = RiderVehicleDetailsSerializer(source='rider_vehicle', many=True, read_only=False, required=False)
    code = serializers.CharField(read_only=True)
    drivers_license_img = serializers.FileField(required=True)

    class Meta:
        model = Rider
        fields = [
            "id",
            "code",
            "first_name",
            "middle_name",
            "last_name",
            "mobile_no",
            "email_address",
            "drivers_license_no",
            "drivers_license_no_expiration_date",
            "drivers_license_img",
            "application_status",
            "status",
            "vehicle_details"
        ]