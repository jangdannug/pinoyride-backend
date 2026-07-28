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
    pr_wallet_details = serializers.SerializerMethodField()

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
            "is_login",
            "customer_address",
            "ekyc_details",
            "wallet_details",
            "pr_wallet_details"
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
        """
        Get EKYC details from TopPhEkycDetails table.
        If ekyc_request_user_id is empty or record doesn't exist, fallback to customer's own details.
        When source is 'customer_profile', only populate basic fields and leave others empty.
        """
        # Helper function to get empty ekyc details with customer's basic info
        def get_customer_profile_ekyc(customer_obj):
            return {
                'id': None,
                'generate_request_user_id': '',
                'kyc_id': '',
                'first_name': customer_obj.fname or '',
                'middle_name': customer_obj.mname or '',
                'last_name': customer_obj.lname or '',
                'email_address': customer_obj.email or '',
                'mobile_no': customer_obj.mobile or '',
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
                'source': 'customer_profile'
            }

        # Check if ekyc_request_user_id exists and is not empty
        if not obj.ekyc_request_user_id or obj.ekyc_request_user_id.strip() == '':
            # Fallback to customer's own details
            return get_customer_profile_ekyc(obj)

        try:
            record = TopPhEkycDetails.objects.get(generate_request_user_id=obj.ekyc_request_user_id)
            data = TopPhEkycDetailsSerializer(record).data
            data['source'] = 'top_ph_ekyc'
            return data
        except TopPhEkycDetails.DoesNotExist:
            # Fallback to customer's own details if EKYC record not found
            return get_customer_profile_ekyc(obj)
        
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

        wallet = Wallet.objects.filter(user_id=obj.id, user_type='customer', type='user-wallet').first()
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


    def get_pr_wallet_details(self, obj):
        # Safely handle if wallet doesn't exist yet
        avail_balance = 0
        wallet_details = {}

        wallet = Wallet.objects.filter(user_id=obj.id, user_type='customer', type='pr-user-wallet').first()
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
        