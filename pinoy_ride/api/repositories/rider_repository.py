from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Count, Avg, Sum, F, Exists, OuterRef, Subquery
from django.db.models.functions import Concat, Cast
from django.db.models import FloatField, CharField
from api.models.rider_model import Rider
from api.models.booking_model import Booking
from api.models.booking_ratings_model import BookingRatings
from api.models.ignored_booking_model import IgnoredBooking
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.models.top_ph_ekyc_details_model import TopPhEkycDetails
from api.serializers import (
    PartialRiderSerializer
)
from django.db import transaction
from django.utils.timezone import now

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
            drivers_license_no_expiration_date=(
                rider.get("drivers_license_no_expiration_date") or None
            ),
            ekyc_request_user_id=rider.get("ekyc_request_user_id", ""),
            application_status=rider.get("application_status", 0),
            status=rider.get("status", 0),
            is_success_kyc=rider.get("is_success_kyc", 0)
        )

        new_rider.drivers_license_img = rider.get("drivers_license_img", "")

        new_rider.save()
        return new_rider

    @staticmethod
    @transaction.atomic
    def update_rider_details(rider_instance, personal_details):
        
        rider_instance.drivers_license_no = personal_details.get("drivers_license_no", "")
        rider_instance.drivers_license_no_expiration_date = personal_details.get("drivers_license_no_expiration_date", "")
        rider_instance.drivers_license_img = personal_details.get("drivers_license_img", "")
        
        rider_instance.save()
        
        return rider_instance

    @staticmethod
    def check_rider_by_request_user_id(request_user_id):
        """Get rider ekyc request user id"""

        ## get active rider
        try:
            return Rider.objects.get(ekyc_request_user_id=request_user_id, application_status=1, status=1)
        except Rider.DoesNotExist:
            return None
        

    @staticmethod
    def check_rider_by_mobile(rider):
        """Get rider by mobile"""

        ## get active rider
        try:
            return Rider.objects.get(mobile_no=rider.get("mobile_no", ""), application_status=1, status=1)
        except Rider.DoesNotExist:
            return None
        

    @staticmethod
    def check_rider_by_mobile_kyc(rider):
        """Get rider by mobile with success kyc - checks both 09+10digits and 63+10digits formats"""

        mobile_no = rider.get("mobile_no", "")

        ## get active rider - check both formats
        try:
            return Rider.objects.get(mobile_no=mobile_no, application_status=1, status=1, is_success_kyc=1)
        except Rider.DoesNotExist:
            pass

        # If not found, try with 09 prefix (convert 63 to 09)
        if mobile_no.startswith('63'):
            mobile_no_09 = '0' + mobile_no[2:]  # 63... -> 09...
            try:
                return Rider.objects.get(mobile_no=mobile_no_09, application_status=1, status=1, is_success_kyc=1)
            except Rider.DoesNotExist:
                pass

        # If not found, try with 63 prefix (convert 09 to 63)
        original_mobile = rider.get("mobile_no", "")
        if original_mobile.startswith('09'):
            mobile_no_63 = '63' + original_mobile[2:]  # 09... -> 63...
            try:
                return Rider.objects.get(mobile_no=mobile_no_63, application_status=1, status=1, is_success_kyc=1)
            except Rider.DoesNotExist:
                pass

        return None


    @staticmethod
    def check_rider_mobile_exists_for_login(mobile_no):
        """Check if rider exists with given mobile number - for login validation"""

        ## Check if any rider exists with this mobile (excluding soft-deleted)
        try:
            return Rider.objects.filter(mobile_no=mobile_no, deleted_at__isnull=True).exists()
        except:
            pass

        # If not found with original format, try with 09 prefix (convert 63 to 09)
        if mobile_no.startswith('63'):
            mobile_no_09 = '0' + mobile_no[2:]  # 63... -> 09...
            try:
                return Rider.objects.filter(mobile_no=mobile_no_09, deleted_at__isnull=True).exists()
            except:
                pass

        # If not found, try with 63 prefix (convert 09 to 63)
        if mobile_no.startswith('09'):
            mobile_no_63 = '63' + mobile_no[2:]  # 09... -> 63...
            try:
                return Rider.objects.filter(mobile_no=mobile_no_63, deleted_at__isnull=True).exists()
            except:
                pass

        return False


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
        """Retrieve paginated rider list with optional search query and filters."""

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

        # application_status = 1 (active riders)
        riders = (
            Rider.objects
            .filter(application_status='1')
            .prefetch_related('rider_vehicle')  # Prefetch vehicle details for filtering
            .annotate(
                # Annotate full_name for search (first_name + middle_name + last_name)
                full_name=Concat(
                    F('first_name'),
                    Value(' '),
                    F('middle_name'),
                    Value(' '),
                    F('last_name'),
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
                riders = riders.filter(current_location__icontains=filters["current_location"])

            # Filter by vehicle type
            if "vehicle_type" in filters and filters["vehicle_type"]:
                riders = riders.filter(rider_vehicle__v_type=filters["vehicle_type"])

            # Filter by vehicle brand
            if "vehicle_brand" in filters and filters["vehicle_brand"]:
                riders = riders.filter(rider_vehicle__v_brand__icontains=filters["vehicle_brand"])

            # Filter by EKYC full name (ekyc_first_name + ekyc_middle_name + ekyc_last_name)
            if "ekyc_full_name" in filters and filters["ekyc_full_name"]:
                riders = riders.filter(ekyc_full_name__icontains=filters["ekyc_full_name"])

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
                    Q(first_name__icontains=term)
                    | Q(middle_name__icontains=term)
                    | Q(last_name__icontains=term)
                    | Q(full_name__icontains=term)  # Search in concatenated full name
                    | Q(code__icontains=term)
                    | Q(mobile_no__icontains=term)
                    | Q(current_location__icontains=term)
                    | Q(rider_vehicle__v_type__icontains=term)
                    | Q(rider_vehicle__v_brand__icontains=term)
                    | Q(rider_vehicle__v_model__icontains=term)
                    | Q(rider_vehicle__v_plate_number__icontains=term)
                    # Search in EKYC details
                    | Exists(ekyc_first_name)
                    | Exists(ekyc_middle_name)
                    | Exists(ekyc_last_name)
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
    def update_rider_coordinates(rider_instance, rider_lat, rider_long, current_location=None):

        rider_instance.current_lat = rider_lat
        rider_instance.current_long = rider_long
        if current_location:
            rider_instance.current_location = current_location
        rider_instance.save()

        return rider_instance

    @staticmethod
    @transaction.atomic
    def update_rider_available_status(rider_instance, status):
        
        rider_instance.is_available = status
        rider_instance.save()
        
        return rider_instance

    
    @staticmethod
    @transaction.atomic
    def update_rider_online_status(rider_instance, status):
        from django.utils.timezone import now

        # Convert to integer if status is string
        status_int = int(status) if isinstance(status, str) else status

        rider_instance.is_online = status_int

        # Update datetime fields based on status
        if status_int == 1:  # Online
            rider_instance.last_online_datetime = now()
        elif status_int == 0:  # Offline
            rider_instance.last_offline_datetime = now()

        rider_instance.save()

        return rider_instance
    
    @staticmethod
    @transaction.atomic
    def update_auto_accept(rider_instance, status):
        
        rider_instance.auto_accept = status
        rider_instance.save()
        
        return rider_instance
    

    @staticmethod
    @transaction.atomic
    def delete_rider(rider_instance, auth_user_id):

        rider_instance.deleted_at = now()
        rider_instance.updated_by = auth_user_id
        rider_instance.save()

        return rider_instance


    @staticmethod
    @transaction.atomic
    def update_firebase_token(rider_instance, firebase_token):
        """Update rider firebase token"""

        rider_instance.firebase_token = firebase_token
        rider_instance.save()

        return rider_instance


    @staticmethod
    def get_rider_service_details(rider_id):
        """Get rider service details including acceptance rate, ratings, and cancellation rate"""

        # Get total booking opportunities (accepted + ignored + pending bookings)
        # Count of bookings where rider is assigned (status >= 1) OR rider ignored
        accepted_count = Booking.objects.filter(
            rider_id=rider_id,
            status__gte=1  # Accepted or beyond
        ).count()

        ignored_count = IgnoredBooking.objects.filter(
            rider_id=rider_id
        ).count()

        total_opportunities = accepted_count + ignored_count

        # Calculate acceptance rate
        if total_opportunities > 0:
            acceptance_rate = round((accepted_count / total_opportunities) * 100, 2)
        else:
            acceptance_rate = 0.00

        # Get ratings average from booking_ratings
        # Cast rate (CharField) to DecimalField before averaging
        ratings_data = BookingRatings.objects.filter(
            booking__rider_id=rider_id
        ).aggregate(
            average_rating=Avg(Cast('rate', FloatField())),
            total_ratings=Count('id')
        )

        average_rating = float(ratings_data['average_rating']) if ratings_data['average_rating'] else 0.0
        total_ratings = ratings_data['total_ratings'] or 0

        # Get cancellation rate (bookings cancelled by rider - status 4)
        # Status 4 means completed/cancelled by customer, but based on booking_view code:
        # status 4 in update_status_for_customer means cancelled
        # We need to count bookings where rider accepted then was cancelled

        cancelled_count = Booking.objects.filter(
            rider_id=rider_id,
            status=4  # Cancelled
        ).count()

        total_accepted = accepted_count
        if total_accepted > 0:
            cancellation_rate = round((cancelled_count / total_accepted) * 100, 2)
        else:
            cancellation_rate = 0.00

        return {
            "acceptance_rate": acceptance_rate,
            "accepted_bookings": accepted_count,
            "ignored_bookings": ignored_count,
            "total_opportunities": total_opportunities,
            "average_rating": round(average_rating, 2),
            "total_ratings": total_ratings,
            "cancellation_rate": cancellation_rate,
            "cancelled_bookings": cancelled_count,
            "total_accepted_bookings": total_accepted
        }


    @staticmethod
    @transaction.atomic
    def save_ignored_booking(rider_id, booking_id):
        """Record when a rider ignores a booking"""

        ignored_booking = IgnoredBooking.objects.create(
            rider_id=rider_id,
            booking_id=booking_id,
            status=0
        )

        return ignored_booking