from rest_framework import serializers
from api.models import Rider, TopPhEkycDetails
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer
from .rider_address_serializer import RiderAddressSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer

class PartialRiderSerializer(serializers.ModelSerializer):

    vehicle_details = RiderVehicleDetailsSerializer(source='rider_vehicle', many=True, read_only=False, required=False)
    code = serializers.CharField(read_only=True)
    drivers_license_img = serializers.FileField(required=True)
    rider_address = serializers.SerializerMethodField()
    ekyc_details = serializers.SerializerMethodField()

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
            "auto_accept",
            "vehicle_details",
            "rider_address",
            "ekyc_details"
        ]


    def get_rider_address(self, obj):
        # get the related table rider_address
        address = obj.rider_address.filter(type=1).first()
        if address:
            return RiderAddressSerializer(address).data
        return {}
    

    def get_ekyc_details(self, obj):
        try:
            record = TopPhEkycDetails.objects.get(generate_request_user_id=obj.ekyc_request_user_id)
            return TopPhEkycDetailsSerializer(record).data
        except TopPhEkycDetails.DoesNotExist:
            return None