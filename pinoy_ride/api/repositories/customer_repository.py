from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, F, Exists, OuterRef, Subquery
from django.db.models.functions import Concat
from django.db.models import CharField
from api.models.customer_model import Customer
from api.models.top_ph_ekyc_details_model import TopPhEkycDetails
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
            ekyc_request_user_id=customer.get("ekyc_request_user_id", ""),
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
    def check_customer_by_mobile_kyc(customer):
        """Get customer by mobile with is_success_kyc"""
        try:
            return Customer.objects.get(mobile=customer.get("mobile_no", ""), is_success_kyc=1, status=1)
        except Customer.DoesNotExist:
            return None


    @staticmethod
    def check_customer_mobile_exists_for_login(mobile_no):
        """Check if customer exists with given mobile number - for login validation"""

        ## Check if any customer exists with this mobile (excluding soft-deleted)
        try:
            return Customer.objects.filter(mobile=mobile_no, deleted_at__isnull=True).exists()
        except:
            return False

    @staticmethod
    def get_customer_by_mobile_for_login(mobile_no):
        """Get customer by mobile number for login validation - checks both 09 and 63 formats"""

        from api.models import Customer

        ## Try to get customer with original format (excluding soft-deleted)
        try:
            return Customer.objects.get(mobile=mobile_no, deleted_at__isnull=True)
        except Customer.DoesNotExist:
            pass

        # If not found with original format, try with 09 prefix (convert 63 to 09)
        if mobile_no.startswith('63'):
            mobile_no_09 = '0' + mobile_no[2:]  # 63... -> 09...
            try:
                return Customer.objects.get(mobile=mobile_no_09, deleted_at__isnull=True)
            except Customer.DoesNotExist:
                pass

        # If not found, try with 63 prefix (convert 09 to 63)
        if mobile_no.startswith('09'):
            mobile_no_63 = '63' + mobile_no[2:]  # 09... -> 63...
            try:
                return Customer.objects.get(mobile=mobile_no_63, deleted_at__isnull=True)
            except Customer.DoesNotExist:
                pass

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
        """Retrieve paginated customer list with optional search query and filters."""

        # Subquery to get EKYC full name (concatenated from TopPhEkycDetails)
        ekyc_full_name_subquery = TopPhEkycDetails.objects.filter(
            generate_request_user_id=OuterRef('ekyc_request_user_id')
        ).annotate(
            ekyc_concat=Concat(
                F('first_name'),
                Value(' '),
                F('middle_name'),
                Value(' '),
                F('last_name'),
                output_field=CharField()
            )
        ).values('ekyc_concat')[:1]

        customers = (
            Customer.objects
            .annotate(
                # Annotate full_name for search (fname + mname + lname)
                full_name=Concat(
                    F('fname'),
                    Value(' '),
                    F('mname'),
                    Value(' '),
                    F('lname'),
                    output_field=CharField()
                ),
                # Annotate EKYC full name from TopPhEkycDetails
                ekyc_full_name=Subquery(ekyc_full_name_subquery, output_field=CharField())
            )
            .order_by(sort_by)
        )

        # Apply filters
        if filters:
            # Filter by current location
            if "current_location" in filters and filters["current_location"]:
                customers = customers.filter(current_location__icontains=filters["current_location"])

            # Filter by EKYC full name (ekyc_first_name + ekyc_middle_name + ekyc_last_name)
            if "ekyc_full_name" in filters and filters["ekyc_full_name"]:
                customers = customers.filter(ekyc_full_name__icontains=filters["ekyc_full_name"])

        if search_query:
            search_terms = search_query.split()
            query_filter = Q()

            for term in search_terms:
                # Build subqueries for EKYC details
                ekyc_first_name = TopPhEkycDetails.objects.filter(
                    generate_request_user_id=OuterRef('ekyc_request_user_id'),
                    first_name__icontains=term
                )
                ekyc_middle_name = TopPhEkycDetails.objects.filter(
                    generate_request_user_id=OuterRef('ekyc_request_user_id'),
                    middle_name__icontains=term
                )
                ekyc_last_name = TopPhEkycDetails.objects.filter(
                    generate_request_user_id=OuterRef('ekyc_request_user_id'),
                    last_name__icontains=term
                )

                query_filter |= (
                    Q(code__icontains=term)
                    | Q(fname__icontains=term)
                    | Q(mname__icontains=term)
                    | Q(lname__icontains=term)
                    | Q(full_name__icontains=term)  # Search in concatenated full name
                    | Q(mobile__icontains=term)
                    | Q(current_location__icontains=term)
                    # Search in EKYC details
                    | Exists(ekyc_first_name)
                    | Exists(ekyc_middle_name)
                    | Exists(ekyc_last_name)
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


    @staticmethod
    @transaction.atomic
    def update_firebase_token(customer_instance, firebase_token):
        """Update customer firebase token"""

        customer_instance.firebase_token = firebase_token
        customer_instance.save()

        return customer_instance


    @staticmethod
    @transaction.atomic
    def update_login_status(customer_instance, status):
        """Update customer login status"""

        customer_instance.is_login = status
        customer_instance.save()

        return customer_instance


    @staticmethod
    @transaction.atomic
    def update_coordinates(customer_instance, customer_lat, customer_long, current_location=None):
        """Update customer coordinates"""

        customer_instance.current_lat = customer_lat
        customer_instance.current_long = customer_long
        if current_location:
            customer_instance.current_location = current_location
        customer_instance.save()

        return customer_instance


    @staticmethod
    def check_rider_logged_in_by_mobile(mobile_no):
        """Check if rider exists with given mobile number and is_login=1"""

        from api.models.rider_model import Rider

        ## Check if any rider exists with this mobile and is_login=1 (excluding soft-deleted)
        try:
            return Rider.objects.filter(mobile_no=mobile_no, is_login=1, deleted_at__isnull=True).exists()
        except:
            pass

        # If not found with original format, try with 09 prefix (convert 63 to 09)
        if mobile_no.startswith('63'):
            mobile_no_09 = '0' + mobile_no[2:]  # 63... -> 09...
            try:
                return Rider.objects.filter(mobile_no=mobile_no_09, is_login=1, deleted_at__isnull=True).exists()
            except:
                pass

        # If not found, try with 63 prefix (convert 09 to 63)
        if mobile_no.startswith('09'):
            mobile_no_63 = '63' + mobile_no[2:]  # 09... -> 63...
            try:
                return Rider.objects.filter(mobile_no=mobile_no_63, is_login=1, deleted_at__isnull=True).exists()
            except:
                pass

        return False