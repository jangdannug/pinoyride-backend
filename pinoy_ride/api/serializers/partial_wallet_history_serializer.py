from rest_framework import serializers
from api.models import Rider, Customer, WalletHistory
from .rider_serializer import RiderSerializer
from .customer_serializer import CustomerSerializer

class PartiallWalletHistorySerializer(serializers.ModelSerializer):

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = WalletHistory
        fields = [
            "id",
            "wallet_id",
            "description",
            "type",
            "amount"
        ]