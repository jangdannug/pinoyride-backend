from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.rider_model import Rider
from api.serializers import (
    PartialRiderSerializer
)
from django.db import transaction

class RiderRepository:
    
    @staticmethod
    @transaction.atomic
    def create(rider):
        new_rider = Rider.objects.create(
            first_name=rider.get("first_name", ""),
            middle_name=rider.get("middle_name", ""),
            last_name=rider.get("last_name", ""),
            mobile_no=rider.get("mobile_no", ""),
            email_address=rider.get("email_address", ""),
            drivers_license_no=rider.get("drivers_license_no", ""),
            drivers_license_no_expiration_date=rider.get("drivers_license_no_expiration_date", "")
        )

        new_rider.drivers_license_img = rider.get("drivers_license_img", "")

        new_rider.save()
        return new_rider


    @staticmethod
    def check_rider_by_mobile(rider):
        """Get rider by mobile"""

        ## get active rider
        try:
            return Rider.objects.get(mobile_no=rider.get("mobile_no", ""), application_status=1, status=1)
        except Rider.DoesNotExist:
            return None


    @staticmethod
    def get_by_id(rider_id):
        """Get rider by id"""
        try:
            return Rider.objects.get(id=rider_id)
        except Rider.DoesNotExist:
            return None

    
    @staticmethod
    def get_available_rider(rider_id):
        """Get rider by id"""
        try:
            return Rider.objects.get(id=rider_id, is_available=1)
        except Rider.DoesNotExist:
            return None

    # exclude application_status = 1
    @staticmethod
    def get_applicant_by_id(rider_id):
        """Get rider applicant by id"""
        try:
            return Rider.objects.exclude(application_status='1').get(id=rider_id)
        except Rider.DoesNotExist:
            return None




    @staticmethod
    def admin_rider_applicants(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated rider applicants with optional search query."""

        # exclude application_status = 1
        riders = (
            Rider.objects
            .exclude(application_status='1')
            .annotate()
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
                    Q(first_name__icontains=term)
                    | Q(middle_name__icontains=term)
                    | Q(last_name__icontains=term)
                )

            riders = riders.filter(query_filter).distinct()

        paginator = Paginator(riders, page_size)
        page = paginator.get_page(page_number)

        serialized_riders = PartialRiderSerializer(
            page.object_list, many=True
        ).data

        return {
            "riders": serialized_riders,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }

    
    @staticmethod
    @transaction.atomic
    def update_rider_applicant_status(rider_instance, applicant_status, auth_user_id):
        
        if applicant_status == '1':
            rider_status = '1'
        else:
            rider_status = '0'

        rider_instance.application_status = applicant_status
        rider_instance.status = rider_status
        rider_instance.updated_by= auth_user_id
        rider_instance.save()
        
        return rider_instance


    @staticmethod
    def admin_riders_list(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated rider list with optional search query."""

        # application_status = 1
        riders = (
            Rider.objects
            .filter(application_status='1', status='1')
            .annotate()
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
                    Q(first_name__icontains=term)
                    | Q(middle_name__icontains=term)
                    | Q(last_name__icontains=term)
                )

            riders = riders.filter(query_filter).distinct()

        paginator = Paginator(riders, page_size)
        page = paginator.get_page(page_number)

        serialized_riders = PartialRiderSerializer(
            page.object_list, many=True
        ).data

        return {
            "riders": serialized_riders,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }


    @staticmethod
    @transaction.atomic
    def update_rider_status(rider_instance, rider_status, auth_user_id):
        
        rider_instance.status = rider_status
        rider_instance.updated_by = auth_user_id
        rider_instance.save()
        
        return rider_instance


    @staticmethod
    @transaction.atomic
    def update_rider_available_status(rider_instance, status):
        
        rider_instance.is_available = status
        rider_instance.save()
        
        return rider_instance