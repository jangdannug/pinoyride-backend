from rest_framework import serializers
from django.db import models as dj_models
from api.models import RiderVehicleDetails, Booking
from api.utils.vehicle_plate_utils import (
    ALLOWED_VEHICLE_TYPES,
    DUPLICATE_PLATE_MESSAGE,
    normalize_plate_number,
    plate_compare_key,
)
import os


class RiderVehicleDetailsListSerializer(serializers.ListSerializer):
    """Always return a rider's vehicles newest first (created_at desc, id desc as tiebreaker)."""

    def to_representation(self, data):
        iterable = data.all() if isinstance(data, dj_models.manager.BaseManager) else data
        ordered = sorted(iterable, key=lambda v: (v.created_at, v.id), reverse=True)
        return super().to_representation(ordered)


class RiderVehicleDetailsSerializer(serializers.ModelSerializer):

    type = serializers.CharField(source='v_type', required=True)
    brand = serializers.CharField(source='v_brand', required=True)
    model = serializers.CharField(source='v_model', required=True)
    color = serializers.CharField(source='v_color', required=True)
    plate_number = serializers.CharField(source='v_plate_number', required=True)
    or_cr_img = serializers.FileField(source='v_or_cr_img', required=False, allow_null=True)
    vehicle_img = serializers.FileField(source='v_vehicle_img', required=False, allow_null=True)
    or_cr_img_pretty = serializers.SerializerMethodField()
    vehicle_img_pretty = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    used_in_completed_transactions = serializers.SerializerMethodField()

    class Meta:
        model = RiderVehicleDetails
        list_serializer_class = RiderVehicleDetailsListSerializer
        fields = [
            "id",
            "rider_id",
            "type",
            "brand",
            "model",
            "color",
            "plate_number",
            "status",
            "is_current",
            "or_cr_img",
            "vehicle_img",
            "or_cr_img_pretty",
            "vehicle_img_pretty",
            "can_delete",
            "used_in_completed_transactions",
        ]

    def validate_type(self, value):
        type_str = str(value).strip()
        if type_str not in ALLOWED_VEHICLE_TYPES:
            raise serializers.ValidationError(
                "Invalid vehicle type. Allowed values: 1 (Motorcycle), "
                "2 (Car 4 Seaters), 3 (Car 6 Seaters)."
            )
        return type_str

    def validate_plate_number(self, value):
        normalized = normalize_plate_number(value)
        if not normalized:
            raise serializers.ValidationError("Plate number is required.")

        # Duplicate check is opt-in (manage_vehicle). The apply/documents
        # endpoints reuse this serializer for an existing rider's own vehicle
        # without a vehicle_id, so checking there would reject their own plate.
        if not self.context.get("check_duplicate_plate"):
            return normalized

        key = plate_compare_key(normalized)
        exclude_id = self.context.get("vehicle_id")
        qs = RiderVehicleDetails.objects.filter(deleted_at__isnull=True)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)

        for plate in qs.values_list("v_plate_number", flat=True):
            if plate_compare_key(plate) == key:
                raise serializers.ValidationError(DUPLICATE_PLATE_MESSAGE)

        return normalized

    def validate_brand(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Brand is required.")
        return str(value).strip()

    def validate_model(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Model is required.")
        return str(value).strip()

    def validate_color(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Color is required.")
        return str(value).strip()

    def _has_completed_trips(self, obj):
        if not obj.rider_id or not obj.v_type:
            return False
        return Booking.objects.filter(
            rider_id=obj.rider_id,
            status=3,
            deleted_at__isnull=True,
            booking_type=str(obj.v_type),
        ).exists()

    def get_used_in_completed_transactions(self, obj):
        return self._has_completed_trips(obj)

    def get_can_delete(self, obj):
        return not self._has_completed_trips(obj)

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
