from django.db import transaction
from api.models import Customer
import datetime
from api.models import (
    Price,
)
from django.db.models import Func, F, Value, CharField
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.db.models import Q, Max, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Concat
from django.utils.timezone import now
from datetime import timedelta
from api.serializers import (
    PriceSerializer, PartialPriceSerializer
)


class PriceRepository:
   
    @staticmethod
    @transaction.atomic
    def create(price, auth_user_id):
        """Creates new price."""

        return Price.objects.create(
            price=price.get("price", ""),
            km=price.get("km", ""),
            time_travel=price.get("time_travel", ""),
            exceed_time_travel_price=price.get("exceed_time_travel_price", ""),
            added_by=auth_user_id
        )
    

    @staticmethod
    def get_by_id(price_id):
        """Fetch price"""
        try:
            return Price.objects.get(id=price_id)
        except Price.DoesNotExist:
            return None


    @staticmethod
    @transaction.atomic
    def update_price(price_instance, update_data):
        
        price_instance.price = update_data.get("price", "")
        price_instance.km = update_data.get("km", "")
        price_instance.time_travel = update_data.get("time_travel", "")
        price_instance.exceed_time_travel_price = update_data.get("exceed_time_travel_price", "")
        price_instance.save()

        return price_instance


    @staticmethod
    @transaction.atomic
    def update_price_status(price_instance, price_status):
        
        price_instance.status = price_status
        price_instance.save()
        
        return price_instance

    
    @staticmethod
    def admin_price_list(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated prices with optional search query."""

        prices = (
            Price.objects.annotate()
            .order_by(sort_by)
        )

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
                    Q(km__icontains=term)
                    | Q(id__icontains=term)
                    | Q(price__icontains=term)
                    | Q(time_travel__icontains=term)
                )

            prices = prices.filter(query_filter).distinct()

        paginator = Paginator(prices, page_size)
        page = paginator.get_page(page_number)

        serialized_prices = PartialPriceSerializer(
            page.object_list, many=True
        ).data

        return {
            "prices": serialized_prices,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }