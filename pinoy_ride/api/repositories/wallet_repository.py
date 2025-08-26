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
