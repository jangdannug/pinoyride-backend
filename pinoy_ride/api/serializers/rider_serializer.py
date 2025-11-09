from rest_framework import serializers
from api.models import Rider, Wallet, TopPhEkycDetails
from .rider_vehicle_details_serializer import RiderVehicleDetailsSerializer
from .rider_address_serializer import RiderAddressSerializer
from .partial_wallet_serializer import PartialWalletSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer
from django.db.models import Sum

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
        try:
            record = TopPhEkycDetails.objects.get(generate_request_user_id=obj.ekyc_request_user_id)
            return TopPhEkycDetailsSerializer(record).data
        except TopPhEkycDetails.DoesNotExist:
            return None
    
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
        avail_balance = float(total_credit) - float(total_debit)

        wallet_details['id'] = wallet.id
        wallet_details['user_type'] = wallet.user_type
        wallet_details['wallet_type'] = wallet.type
        wallet_details['avail_balance'] = avail_balance

        return wallet_details
        