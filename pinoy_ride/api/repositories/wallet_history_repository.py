from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Sum, When, Case, F, IntegerField, FloatField
from django.db.models.functions import Concat, Coalesce
from api.models.wallet_history_model import WalletHistory
from api.serializers import (
    WalletHistorySerializer,
    PartiallWalletHistorySerializer
)
from django.db import transaction

class WalletHistoryRepository:
    
    @staticmethod
    @transaction.atomic
    def create(wallet_instance, wallet_history):
        now = timezone.localtime(timezone.now())
        date_now = now.strftime("%Y-%m-%d")
        time_now = now.strftime("%I:%M %p")

        mew_wallet_history = WalletHistory.objects.create(
            wallet=wallet_instance,
            booking_id=wallet_history.get("booking_id", ""),
            type=wallet_history.get("type", ""),
            description=wallet_history.get("description", ""),
            credit_amount=wallet_history.get("credit_amount", 0),
            debit_amount=wallet_history.get("debit_amount", 0),
            tran_type=wallet_history.get("tran_type", ""),
            time_created=time_now,
            date_created=date_now
        )

        mew_wallet_history.save()
        
        return mew_wallet_history

    
    @staticmethod
    def get_all(wallet_id):
        """Retrieve wallet history"""

        wallet_history = (
            WalletHistory.objects
            .filter(wallet_id=wallet_id)
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

        totals = WalletHistory.objects.filter(wallet_id=wallet_id).aggregate(
            total_debit=Sum("debit_amount", filter=Q(type="debit")),
            total_credit=Sum("credit_amount", filter=Q(type="credit")),
        )
    
        return {
            "total_debit": totals["total_debit"] or 0,
            "total_credit": totals["total_credit"] or 0,
        }
    
    @staticmethod
    def get_wallet_history(wallet_instance, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated user's wallet history with optional search query."""

        # Get credit_amount = credit otherwise get debit_amount
        wallet_history = WalletHistory.objects.filter(wallet_id=wallet_instance.id).annotate(
        amount=Case(
            When(type='credit', then=F('credit_amount')),
            When(type='debit', then=F('debit_amount')),
            default=Value(0),
            output_field=FloatField()
        )
        ).order_by(sort_by)

        # if filters:
        #     if "name_filter" in filters and filters["name_filter"]:
        #         promos = promos.filter(
        #             name=filters["name_filter"]
        #         )

        if search_query:
            search_terms = search_query.split()
            query_filter = Q()

            for term in search_terms:
                query_filter |= (
                    Q(description__icontains=term)
                    | Q(type__icontains=term)
                )

            wallet_history = wallet_history.filter(query_filter).distinct()

        paginator = Paginator(wallet_history, page_size)
        page = paginator.get_page(page_number)

        serialized_wallet_history = PartiallWalletHistorySerializer(
            page.object_list, many=True
        ).data

        return {
            "wallet_history": serialized_wallet_history,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }