from rest_framework import serializers
from api.models import Rider, Customer, Wallet

class PartialWalletSerializer(serializers.ModelSerializer):

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
            "status"
        ]
    


       