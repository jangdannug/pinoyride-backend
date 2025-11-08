from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.customer_model import Customer
from api.serializers import (
    PartialCustomerSerializer
)
from django.db import transaction

class CustomerRepository:
    
    @staticmethod
    @transaction.atomic
    def create(customer):
        new_customer = Customer.objects.create(
            customer_type=customer.get("customer_type", ""),
            fname=customer.get("fname", ""),
            mname=customer.get("mname", ""),
            lname=customer.get("lname", ""),
            mobile=customer.get("mobile", ""),
            email=customer.get("email", ""),
            login_type=customer.get("login_type", ""),
            status=customer.get("status", ""),
            is_success_kyc=customer.get("is_success_kyc", ""),
        )

        new_customer.save()
        return new_customer


    @staticmethod
    def check_customer_by_mobile(customer):
        """Get customer by mobile"""
        try:
            return Customer.objects.get(mobile=customer.get("mobile_no", ""))
        except Customer.DoesNotExist:
            return None


    @staticmethod
    def get_customer_by_id(customer_id):
        """Get customer by id"""
        try:
            return Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return None


    @staticmethod
    def admin_customer_list(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated customer list with optional search query."""

        customers = (
            Customer.objects
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

            customers = customers.filter(query_filter).distinct()

        paginator = Paginator(customers, page_size)
        page = paginator.get_page(page_number)

        serialized_customers = PartialCustomerSerializer(
            page.object_list, many=True
        ).data

        return {
            "customers": serialized_customers,
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
    def update_customer_status(customer_instance, customer_status, auth_user_id):
        
        customer_instance.status = customer_status
        customer_instance.updated_by = auth_user_id
        customer_instance.save()
        
        return customer_instance