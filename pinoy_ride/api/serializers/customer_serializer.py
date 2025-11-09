from rest_framework import serializers
from api.models import Customer, TopPhEkycDetails, Wallet
from .customer_address_serializer import CustomerAddressSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer
from django.db.models import Sum

class CustomerSerializer(serializers.ModelSerializer):

    code = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    email = serializers.CharField(required=True)
    customer_address = serializers.SerializerMethodField()
    ekyc_details = serializers.SerializerMethodField()
    wallet_details = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "code",
            "fname",
            "mname",
            "lname",
            "mobile",
            "email",
            "status",
            "customer_address",
            "ekyc_details",
            "wallet_details"
        ]
    
    def validate_email(self, value):
        """Validate the email_address field to ensure it is unique (excluding soft-deleted records)"""
        queryset = Customer.objects.filter(email=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This email address already exists.")
        
        return value


    def validate_mobile(self, value):
        """Validate the mobile_no to ensure it is unique (excluding soft-deleted records)"""
        queryset = Customer.objects.filter(mobile=value, deleted_at__isnull=True)

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
        
    def get_customer_address(self, obj):
        # get the related table customer_address
        address = obj.customer_address
        if address:
            return CustomerAddressSerializer(address, many=True).data
        return {}

      
    def get_wallet_details(self, obj):
        # Safely handle if wallet doesn't exist yet
        avail_balance = 0
        wallet_details = {}

        wallet = Wallet.objects.filter(user_id=obj.id, user_type='customer').first()
        if not wallet:
            return wallet_details
        
        total_credit = wallet.wallet_ref.aggregate(total=Sum('credit_amount'))['total'] or 0
        total_debit = wallet.wallet_ref.aggregate(total=Sum('debit_amount'))['total'] or 0
        avail_balance = float(total_credit) - float(total_debit)

        wallet_details['id'] = wallet.id
        wallet_details['user_type'] = wallet.user_type
        wallet_details['wallet_type'] = wallet.type
        wallet_details['avail_balance'] = avail_balance

        return wallet_details
        