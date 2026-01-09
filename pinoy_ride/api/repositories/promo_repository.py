from django.db import transaction
from api.models import Customer
import datetime
from api.models import (
    Promo,
)
from django.db.models import Func, F, Value, CharField
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.db.models import Q, Max, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Concat
from django.utils.timezone import now
from datetime import timedelta
from api.serializers import (
    PromoSerializer, PartialPromoSerializer
)

# Status
# 0 -> Pending (Not yet started)
# 1 -> Active 
# 2 -> Limit reached
# 3 -> Expired

class PromoRepository:
   
    @staticmethod
    @transaction.atomic
    def create(promo, auth_user_id):
        """Creates new promo."""

        return Promo.objects.create(
            code=promo.get("code", ""),
            name=promo.get("name", ""),
            start_date=promo.get("start_date", ""),
            end_date=promo.get("end_date", ""),
            location=promo.get("location", ""),
            no_of_users=promo.get("no_of_users", 0),
            added_by=auth_user_id
        )
    

    @staticmethod
    def get_by_id(promo_id):
        """Fetch promo"""
        try:
            return Promo.objects.get(id=promo_id)
        except Promo.DoesNotExist:
            return None
        
    @staticmethod
    def get_by_code(promo_code):
        """Fetch promo by code"""
        try:
            return Promo.objects.get(code=promo_code)
        except Promo.DoesNotExist:
            return None


    @staticmethod
    @transaction.atomic
    def update_promo(promo_instance, update_data):
        
        promo_instance.code = update_data.get("code", "")
        promo_instance.name = update_data.get("name", "")
        promo_instance.start_date = update_data.get("start_date", "")
        promo_instance.end_date = update_data.get("end_date", "")
        promo_instance.location = update_data.get("location", "")
        promo_instance.no_of_users = update_data.get("no_of_users", 0)
        promo_instance.save()

        return promo_instance


    @staticmethod
    @transaction.atomic
    def update_promo_status(promo_instance, promo_status):
        
        promo_instance.status = promo_status
        promo_instance.save()
        
        return promo_instance
    
    @staticmethod
    def promo_list(customer_id):
        """Retrieve promos"""

        promos = (
            Promo.objects
                .filter(status=1)
                .annotate(
                start_date_pretty=Func(
                    F('start_date'),
                    Value('FMMonth DD, YYYY'),
                    function='TO_CHAR',
                    output_field=CharField()
                ),
            )
            .order_by('-id')
        )


        serialized_promos = PartialPromoSerializer(
            promos, many=True
        ).data

        return {
            "promos": serialized_promos
        }
    

    @staticmethod
    def admin_promo_list(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated promos with optional search query."""

        promos = (
            Promo.objects.annotate(
                start_date_pretty=Func(
                    F('start_date'),
                    Value('FMMonth DD, YYYY'),
                    function='TO_CHAR',
                    output_field=CharField()
                ),
            )
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
                    Q(name__icontains=term)
                )

            promos = promos.filter(query_filter).distinct()

        paginator = Paginator(promos, page_size)
        page = paginator.get_page(page_number)

        serialized_promos = PartialPromoSerializer(
            page.object_list, many=True
        ).data

        return {
            "promos": serialized_promos,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }