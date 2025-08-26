from rest_framework import serializers
from api.models import Rider, Customer, Wallet
from .rider_serializer import RiderSerializer
from .customer_serializer import CustomerSerializer

class WalletSerializer(serializers.ModelSerializer):

    user_details = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            "id",
            "ref_code",
            "user_id",
            "user_type",
            "avail_balance",
            "credit_amount",
            "debit_amount",
            "status",
            "user_details"
        ]
    
    
    def get_user_details(self, obj):

        if obj.user_type == 'rider':
            try:
                rider_details =  Rider.objects.get(id=obj.user_id)
                return RiderSerializer(rider_details).data
            except Rider.DoesNotExist:
                return {}
        else:
            try:
                customer_details = Customer.objects.get(id=obj.user_id)
                return CustomerSerializer(customer_details).data
            except Customer.DoesNotExist:
                return {}




       