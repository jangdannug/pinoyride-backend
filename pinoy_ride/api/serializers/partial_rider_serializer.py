from rest_framework import serializers
from api.models import Rider, TopPhEkycDetails
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer
from .rider_address_serializer import RiderAddressSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer
import os
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
            "current_lat",
            "current_long",
            "current_location",
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
        """
        Get EKYC details from TopPhEkycDetails table.
        If ekyc_request_user_id is empty or record doesn't exist, fallback to rider's own details.
        When source is 'rider_profile', only populate basic fields and leave others empty.
        """
        # Helper function to get empty ekyc details with rider's basic info
        def get_rider_profile_ekyc(rider_obj):
            # Format selfie URL
            selfie_url = ''
            if rider_obj.selfie and hasattr(rider_obj.selfie, 'name'):
                img_name = str(rider_obj.selfie.name)
                if img_name.startswith('http://') or img_name.startswith('https://'):
                    selfie_url = img_name
                else:
                    base_url = os.getenv('IMAGE_BASE_URL', 'http://127.0.0.1:7966/media')
                    selfie_url = f"{base_url}/{img_name}"

            return {
                'id': None,
                'generate_request_user_id': '',
                'kyc_id': '',
                'first_name': rider_obj.first_name or '',
                'middle_name': rider_obj.middle_name or '',
                'last_name': rider_obj.last_name or '',
                'email_address': '',
                'mobile_no': rider_obj.mobile_no or '',
                'date_of_birth': '',
                'place_of_birth': '',
                'nationality': '',
                'gender': '',
                'current_country': '',
                'current_address': '',
                'nature_of_work': '',
                'source_of_fund': '',
                'id_type': '',
                'id_number': '',
                'id_front': '',
                'id_back': '',
                'selfie': selfie_url,
                'status': 0,
                'pretty_mobile_no': '',
                'permanent_address': '',
                'permanent_country': '',
                'create_date': '',
                'source': 'rider_profile'
            }

        # Check if ekyc_request_user_id exists and is not empty
        if not obj.ekyc_request_user_id or obj.ekyc_request_user_id.strip() == '':
            # Fallback to rider's own details
            return get_rider_profile_ekyc(obj)

        try:
            record = TopPhEkycDetails.objects.get(generate_request_user_id=obj.ekyc_request_user_id)
            data = TopPhEkycDetailsSerializer(record).data
            data['source'] = 'top_ph_ekyc'
            return data
        except TopPhEkycDetails.DoesNotExist:
            # Fallback to rider's own details if EKYC record not found
            return get_rider_profile_ekyc(obj)