from rest_framework import serializers
from api.models import PriceConfig


class PriceConfigSerializer(serializers.ModelSerializer):
    """Serializer for PriceConfig model"""

    class Meta:
        model = PriceConfig
        fields = [
            "id",
            "booking_type",
            "booking_type_name",
            "km_basis",
            "minimum_fare",
            "pesos_per_km",
            "pesos_per_km2",
            "booking_fee",
            "commission_percentage",
            "is_active",
            "status",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_booking_type(self, value):
        """Validate booking_type is not empty"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("Booking type is required.")
        return value

    def validate_commission_percentage(self, value):
        """Validate commission_percentage is between 0 and 1"""
        if value < 0 or value > 1:
            raise serializers.ValidationError("Commission percentage must be between 0 and 1 (e.g., 0.15 for 15%).")
        return value

    def validate_km_basis(self, value):
        """Validate km_basis is positive"""
        if value < 0:
            raise serializers.ValidationError("KM basis must be positive.")
        return value

    def validate_minimum_fare(self, value):
        """Validate minimum_fare is positive"""
        if value < 0:
            raise serializers.ValidationError("Minimum fare must be positive.")
        return value


class PriceConfigDetailSerializer(PriceConfigSerializer):
    """Detailed serializer with additional computed fields"""

    commission_display = serializers.SerializerMethodField()

    class Meta(PriceConfigSerializer.Meta):
        fields = PriceConfigSerializer.Meta.fields + ["commission_display"]

    def get_commission_display(self, obj):
        """Return commission as percentage string"""
        return f"{obj.commission_percentage * 100:.1f}%"
