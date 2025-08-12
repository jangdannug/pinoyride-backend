from rest_framework import serializers
from api.models import Rider
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class RiderSerializer(serializers.ModelSerializer):

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
    
    def validate_email_address(self, value):
        """Validate the email_address field to ensure it is unique (excluding soft-deleted records)"""
        queryset = Rider.objects.filter(email_address=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This email address already exists.")
        
        return value


    def validate_mobile_no(self, value):
        """Validate the mobile_no to ensure it is unique (excluding soft-deleted records)"""
        queryset = Rider.objects.filter(mobile_no=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This mobile no already exists.")
        
        return value