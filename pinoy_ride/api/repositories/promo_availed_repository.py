from django.db import transaction
from api.models import Customer
import datetime
from api.models import (
    PromoAvailed,
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

class PromoAvailedRepository:
    
    @staticmethod
    @transaction.atomic
    def create(promo_instance, customer_instance, booking_instance):
        new_promo_availed = PromoAvailed.objects.create(
            promo=promo_instance,
            customer=customer_instance,
            booking=booking_instance
        )

        new_promo_availed.save()
        return new_promo_availed
    
    @staticmethod
    @transaction.atomic
    def check_if_availed(promo_id, customer_id):
        """Check if promo availed"""
        return PromoAvailed.objects.filter(
            promo_id=promo_id,
            customer_id=customer_id,
            status=1
        ).exists()

    @staticmethod
    @transaction.atomic
    def count_promo_availed(promo_id):
        """Count promo availed"""
        availed_count = PromoAvailed.objects.filter(
                    promo_id=promo_id,
                    status=1
                ).count()
                    
        return availed_count
    
    
    @staticmethod
    def get_by_booking_id(booking_id):
        """Fetch promo availed"""
        try:
            return PromoAvailed.objects.get(booking_id=booking_id)
        except PromoAvailed.DoesNotExist:
            return None
        


    @staticmethod
    @transaction.atomic
    def update_promo_availed_status(promo_availed_instance, status):
        
        promo_availed_instance.status = status
        promo_availed_instance.save()
        
        return promo_availed_instance