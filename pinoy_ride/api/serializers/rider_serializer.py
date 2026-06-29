from rest_framework import serializers
from api.models import Rider, Wallet, TopPhEkycDetails
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer
from .rider_address_serializer import RiderAddressSerializer
from .partial_wallet_serializer import PartialWalletSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer
from django.db.models import Sum
from api.utils.customer_utils import CustomUtils

class RiderSerializer(serializers.ModelSerializer):

    vehicle_details = RiderVehicleDetailsSerializer(source='rider_vehicle', many=True, read_only=False, required=False)
    code = serializers.CharField(read_only=True)
    auto_accept = serializers.IntegerField(read_only=True)
    drivers_license_img = serializers.FileField(required=True)
    rider_address = serializers.SerializerMethodField()
    ekyc_details = serializers.SerializerMethodField()
    wallet_details = serializers.SerializerMethodField()

    class Meta:
        model = Rider
        fields = [
            "id",
            "ekyc_request_user_id",
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
            "auto_accept",
            "is_available", # 1 = available, 2 = unavailable
            "is_online",
            "status",
            "ekyc_details",
            "vehicle_details",
            "rider_address",
            "wallet_details"
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

    def get_ekyc_details(self, obj):
        """
        Get EKYC details from TopPhEkycDetails table.
        If ekyc_request_user_id is empty or record doesn't exist, fallback to rider's own details.
        When source is 'rider_profile', only populate basic fields and leave others empty.
        """
        # Helper function to get empty ekyc details with rider's basic info
        def get_rider_profile_ekyc(rider_obj):
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
                'selfie': '',
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
    
    def get_rider_address(self, obj):
        # get the related table rider_address
        address = obj.rider_address.filter(type=1).first()
        if address:
            return RiderAddressSerializer(address).data
        return {}
    
    def get_wallet_details(self, obj):
        # Safely handle if wallet doesn't exist yet
        avail_balance = 0
        wallet_details = {}

        wallet = Wallet.objects.filter(user_id=obj.id, user_type='rider').first()
        if not wallet:
            return wallet_details
        
        # get details in wallet history
        total_credit = wallet.wallet_ref.aggregate(total=Sum('credit_amount'))['total'] or 0
        total_debit = wallet.wallet_ref.aggregate(total=Sum('debit_amount'))['total'] or 0
        avail_balance = round(float(total_credit) - float(total_debit),2)

        wallet_details['id'] = wallet.id
        wallet_details['user_type'] = wallet.user_type
        wallet_details['wallet_type'] = wallet.type
        wallet_details['avail_balance'] = avail_balance

        return wallet_details
        