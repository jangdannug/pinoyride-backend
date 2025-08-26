from rest_framework import serializers
from api.models import Rider, Customer, WalletHistory
from .rider_serializer import RiderSerializer
from .customer_serializer import CustomerSerializer

class WalletHistorySerializer(serializers.ModelSerializer):

    class Meta:
        model = WalletHistory
        fields = [
            "id",
            "wallet_id",
            "description",
            "type",
            "credit_amount",
            "debit_amount",
            "time_created",
            "date_created",
            "status"
        ]
    


       