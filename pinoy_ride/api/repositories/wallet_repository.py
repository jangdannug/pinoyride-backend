from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Sum, FloatField
from django.db.models.functions import Concat, Coalesce
from api.models.wallet_model import Wallet
from api.models.wallet_history_model import WalletHistory
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
    def get_customer_wallet(customer_id):
        """Get customer wallet"""
        try:
            return Wallet.objects.get(user_id=customer_id, user_type='customer', type='user-wallet')
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


    @staticmethod
    def get_wallet_summary(user_id, user_type='customer'):
        """Get wallet summary including current balance, total spent, and total top-ups"""

        # Get the wallet
        try:
            wallet = Wallet.objects.get(user_id=user_id, user_type=user_type, type='user-wallet')
        except Wallet.DoesNotExist:
            # If wallet doesn't exist, return zeros
            return {
                'current_balance': 0.0,
                'total_spent': 0.0,
                'total_topups': 0.0
            }

        # Calculate totals from wallet_history (same as check_balance method)
        totals = WalletHistory.objects.filter(
            wallet_id=wallet.id
        ).aggregate(
            total_credit=Coalesce(Sum('credit_amount', filter=Q(type='credit')), 0, output_field=FloatField()),
            total_debit=Coalesce(Sum('debit_amount', filter=Q(type='debit')), 0, output_field=FloatField())
        )

        total_credit = totals['total_credit'] or 0
        total_debit = totals['total_debit'] or 0

        # Calculate available balance dynamically (credit - debit)
        current_balance = total_credit - total_debit

        return {
            'current_balance': round(current_balance, 2),
            'total_spent': round(total_debit, 2),
            'total_topups': round(total_credit, 2)
        }