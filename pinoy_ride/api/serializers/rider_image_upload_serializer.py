from rest_framework import serializers

class RiderImageUploadSerializer(serializers.Serializer):
    rider_id = serializers.IntegerField(required=True)
    drivers_license_img = serializers.ImageField(required=False, allow_null=True)
    selfie = serializers.ImageField(required=False, allow_null=True)
    v_vehicle_img = serializers.ImageField(required=False, allow_null=True)
    v_or_cr_img = serializers.ImageField(required=False, allow_null=True)
