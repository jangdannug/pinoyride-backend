from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Sum
from django.db.models.functions import Concat
from api.models.pinoy_ride_wallet_history_model import PinoyRideWalletHistory
from api.serializers import (
    WalletHistorySerializer
)
from django.db import transaction

class PinoyRideWalletHistoryRepository:
    
    @staticmethod
    @transaction.atomic
    def create(wallet_instance, wallet_history):
        now = timezone.localtime(timezone.now())
        date_now = now.strftime("%Y-%m-%d")
        time_now = now.strftime("%I:%M %p")

        mew_wallet_history = PinoyRideWalletHistory.objects.create(
            pinoy_ride_wallet=wallet_instance,
            booking_id=wallet_history.get("booking_id", ""),
            type=wallet_history.get("type", ""),
            description=wallet_history.get("description", ""),
            credit_amount=wallet_history.get("credit_amount", 0),
            debit_amount=wallet_history.get("debit_amount", 0),
            time_created=time_now,
            date_created=date_now
        )

        mew_wallet_history.save()
        
        return mew_wallet_history

    
    @staticmethod
    def get_all(wallet_id):
        """Retrieve wallet history"""

        wallet_history = (
            PinoyRideWalletHistory.objects
            .filter(pinoy_ride_wallet_id=wallet_id)
            .order_by("-id")
        )

        serialized_history = WalletHistorySerializer(
            wallet_history, many=True
        ).data

        return {
            "wallet_history": serialized_history
        }


    @staticmethod
    def get_total_debit_credit(wallet_id):
        """Get total debit and credit amounts"""

        totals = PinoyRideWalletHistory.objects.filter(pinoy_ride_wallet_id=wallet_id).aggregate(
            total_debit=Sum("debit_amount", filter=Q(type="debit")),
            total_credit=Sum("credit_amount", filter=Q(type="credit")),
        )
    
        return {
            "total_debit": totals["total_debit"] or 0,
            "total_credit": totals["total_credit"] or 0,
        }