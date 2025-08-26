from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.wallet_history_model import WalletHistory
from api.serializers import (
    PartialCustomerSerializer
)
from django.db import transaction

class WalletHistoryRepository:
    
    @staticmethod
    @transaction.atomic
    def create(wallet_instance, wallet_history):
        mew_wallet_history = WalletHistory.objects.create(
            wallet=wallet_instance,
            type=wallet_history.get("type", ""),
            credit_amount=wallet_history.get("credit_amount", ""),
            debit_amount=wallet_history.get("debit_amount", ""),
            time_created=wallet_history.get("time_created", ""),
            date_created=wallet_history.get("date_created", ""),
        )

        mew_wallet_history.save()
        
        return mew_wallet_history
