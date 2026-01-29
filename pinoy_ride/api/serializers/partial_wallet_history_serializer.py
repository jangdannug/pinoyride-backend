from rest_framework import serializers
from api.models import Rider, Customer, WalletHistory
from .rider_serializer import RiderSerializer
from .customer_serializer import CustomerSerializer
from django.utils import timezone

class PartiallWalletHistorySerializer(serializers.ModelSerializer):

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    create_date = serializers.SerializerMethodField()
    class Meta:
        model = WalletHistory
        fields = [
            "id",
            "wallet_id",
            "description",
            "type",
            "amount",
            "create_date"
        ]


    def get_create_date(self, obj):
        if obj.created_at:
            return timezone.localtime(obj.created_at).strftime("%Y-%m-%d %H:%M:%S")
        return ""