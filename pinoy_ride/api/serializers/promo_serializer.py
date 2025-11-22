from rest_framework import serializers
from api.models import Promo
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer

class PromoSerializer(serializers.ModelSerializer):

    status = serializers.CharField(required=False)
    code = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    location = serializers.CharField(required=True)
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)

    class Meta:
        model = Promo
        fields = [
            "id",
            "code",
            "name",
            "start_date",
            "end_date",
            "location",
            "no_of_users",
            "status"
        ]

    def validate(self, data):
        start = data.get('start_date')
        end = data.get('end_date')

        if start and end and start > end:
            raise serializers.ValidationError("Start date cannot be after end date.")
        
        return data

    def validate_code(self, value):
        """Validate the code field to ensure it is unique (excluding soft-deleted records)"""
        queryset = Promo.objects.filter(code=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This promo code already exists.")
        
        return value


    def validate_name(self, value):
        """Validate the name to ensure it is unique (excluding soft-deleted records)"""
        queryset = Promo.objects.filter(name=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This name already exists.")
        
        return value
