from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.wallet_model import Wallet
from api.serializers import (
    PartialCustomerSerializer
)
from django.db import transaction

class WalletRepository:
    
    @staticmethod
    @transaction.atomic
    def create(wallet_details):
        new_wallet = Wallet.objects.create(
            user_id=wallet_details.get("user_id", ""),
            user_type=wallet_details.get("user_type", ""),
            type=wallet_details.get("type", "")
        )

        new_wallet.save()
        
        return new_wallet


    @staticmethod
    def get_rider_wallet(rider_id):
        """Get rider wallet"""
        try:
            return Wallet.objects.get(user_id=rider_id, user_type='rider', type='user-wallet')
        except Wallet.DoesNotExist:
            return None

    
    @staticmethod
    @transaction.atomic
    def update_balance(wallet_instance, wallet_details):
        
        wallet_instance.credit_amount = wallet_details.get("credit_amount", 0)
        wallet_instance.debit_amount = wallet_details.get("debit_amount", 0)
        wallet_instance.avail_balance = wallet_details.get("avail_balance", 0)
        wallet_instance.save()
        
        return wallet_instance