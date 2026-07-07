from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Exists, OuterRef
from django.db.models.functions import Concat
from api.models.booking_model import Booking
from api.models.ignored_booking_model import IgnoredBooking
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger
import math, random

class BookingRepository:
    
    @staticmethod
    @transaction.atomic
    def create(customer_instance, booking_details):
        
        now = timezone.localtime(timezone.now())
        date_now = now.strftime("%Y-%m-%d")
        time_now = now.strftime("%I:%M %p")

        new_booking = Booking.objects.create(
            customer=customer_instance,
            pickup_location=booking_details.get("pickup_location", ""),
            booking_type=booking_details.get("booking_type", ""),
            dropoff_location=booking_details.get("dropoff_location", ""),
            pickup_lat=booking_details.get("pickup_lat", ""),
            pickup_long=booking_details.get("pickup_long", ""),
            dropoff_lat=booking_details.get("dropoff_lat", ""),
            dropoff_long=booking_details.get("dropoff_long", ""),
            distance_km=booking_details.get("distance_km", ""),
            payment_type=booking_details.get("payment_type", ""),
            note_to_rider=booking_details.get("note_to_rider", ""),
            time_created=time_now,
            date_created=date_now
        )

        new_booking.save()
        return new_booking


    

    @staticmethod
    def pending_list(rider_lat, rider_long, booking_type, rider_id=None):
        """Retrieve list of pending bookings, excluding those ignored by the rider"""
        rider_lat = float(rider_lat)
        rider_long = float(rider_long)
        rider_current_latlong = (rider_lat, rider_long)
        radius_km = 1.5 #0.5 -> 500 meters #3 -> 3000 meters radius

        lat_delta = radius_km / 111  # in degrees
        lng_delta = radius_km / (111 * math.cos(math.radians(rider_lat)))
        lat_range = (rider_lat - lat_delta, rider_lat + lat_delta)
        lng_range = (rider_long - lng_delta, rider_long + lng_delta)

        # Build base query
        bookings_query = Booking.objects.filter(
            status=0,
            pickup_lat__range=lat_range,
            pickup_long__range=lng_range,
            booking_type=booking_type
        )

        # Exclude bookings that this rider has already ignored
        # if rider_id:
        #     # Get list of booking IDs that this rider has ignored
        #     ignored_booking_ids = IgnoredBooking.objects.filter(
        #         rider_id=rider_id
        #     ).values_list('booking_id', flat=True)

        #     if ignored_booking_ids:
        #         bookings_query = bookings_query.exclude(id__in=ignored_booking_ids)

        # Narrow down candidates from DB
        bookings = bookings_query.order_by("-id")[:50]  # limit to 50 candidates

        nearby_bookings = []
        for booking in bookings:
            booking_pickup_point = (booking.pickup_lat, booking.pickup_long)
            distance = geodesic(rider_current_latlong, booking_pickup_point).kilometers
            app_logger(1, str("Distance " + str(booking.id) + " "+str(distance)) , [])
            if distance <= radius_km:
                nearby_bookings.append(booking)


        serialized_bookings = BookingSerializer(nearby_bookings, many=True).data

        return {
            "bookings": serialized_bookings
        }


    @staticmethod
    def random_pending(rider_lat, rider_long):
        """Retrieve random pending booking"""

        rider_lat = float(rider_lat)
        rider_long = float(rider_long)
        rider_current_latlong = (rider_lat, rider_long)

        radius_km = 1.5  # 1.5 km search radius

        lat_delta = radius_km / 111  # in degrees
        lng_delta = radius_km / (111 * math.cos(math.radians(rider_lat)))
        lat_range = (rider_lat - lat_delta, rider_lat + lat_delta)
        lng_range = (rider_long - lng_delta, rider_long + lng_delta)

        # Narrow down candidates from DB
        bookings = (
            Booking.objects
            .filter(status=0, pickup_lat__range=lat_range, pickup_long__range=lng_range)
            .order_by("-id")[:50]  # limit to 50 candidates
        )

        # Precise filtering using geopy
        nearby_bookings = []
        for booking in bookings:
            booking_pickup_point = (booking.pickup_lat, booking.pickup_long)
            distance = geodesic(rider_current_latlong, booking_pickup_point).kilometers
            app_logger(1, str("Distance " + str(booking.id) + " "+str(distance)) +" km" , [])
            if distance <= radius_km:
                nearby_bookings.append(booking)

        if not nearby_bookings:
            serialized_booking =  {}
        else:
            # Choose random 1 booking
            random_booking = random.choice(nearby_bookings)
            serialized_booking = BookingSerializer(random_booking).data

        return serialized_booking


    @staticmethod
    def get_rider_booking_history(rider_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve rider booking history"""
    
        bookings = Booking.objects.filter(rider_id=rider_id).order_by(sort_by)
      
        if search_query:
            search_terms = search_query.split()
            query_filter = Q()

            for term in search_terms:
                query_filter |= (
                    Q(first_name__icontains=term)
                    | Q(middle_name__icontains=term)
                    | Q(last_name__icontains=term)
                )

            bookings = bookings.filter(query_filter).distinct()

        paginator = Paginator(bookings, page_size)
        page = paginator.get_page(page_number)

        serialized_bookings = BookingSerializer(
            page.object_list, many=True
        ).data

        return {
            "bookings": serialized_bookings,
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
    def get_customer_booking_history(customer_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve customer booking history"""

        bookings = Booking.objects.filter(customer_id=customer_id).order_by(sort_by)
      
        if search_query:
            search_terms = search_query.split()
            query_filter = Q()

            for term in search_terms:
                query_filter |= (
                    Q(first_name__icontains=term)
                    | Q(middle_name__icontains=term)
                    | Q(last_name__icontains=term)
                )

            bookings = bookings.filter(query_filter).distinct()

        paginator = Paginator(bookings, page_size)
        page = paginator.get_page(page_number)

        serialized_bookings = BookingSerializer(
            page.object_list, many=True
        ).data

        return {
            "bookings": serialized_bookings,
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
    def get_by_id(booking_id):
        """Get booking by id"""
        try:
            return Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return None

    @staticmethod
    def get_by_rider_and_id(rider_id, booking_id):
        """Get booking by rider id and id"""
        try:
            return Booking.objects.get(id=booking_id, rider_id=rider_id)
        except Booking.DoesNotExist:
            return None
    
    @staticmethod
    def get_by_customer_and_id(customer_id, booking_id):
        """Get booking by customer id and id"""
        try:
            return Booking.objects.get(id=booking_id, customer_id=customer_id)
        except Booking.DoesNotExist:
            return None


    @staticmethod
    @transaction.atomic
    def accept_booking(booking_instance, rider_instance):
        
        try:
            # Lock the row so no one else can update until commit
            booking = Booking.objects.select_for_update().get(
                id=booking_instance.id,
                status=0,
                rider_id__isnull=True
            )
        except Booking.DoesNotExist:
            return None  # already assigned

        booking.status = 1
        booking.updated_by = rider_instance.id
        booking.rider = rider_instance
        booking.save()
        return booking


    @staticmethod
    @transaction.atomic
    def update_booking_status_for_rider(booking_instance, booking_status, rider_instance):
        
        booking_instance.status = booking_status
        booking_instance.updated_by = rider_instance.id
        booking_instance.rider_id = rider_instance
        booking_instance.updated_by_user = 'rider'
        booking_instance.save()
        
        return booking_instance

    
    @staticmethod
    @transaction.atomic
    def update_booking_status_for_customer(booking_instance, booking_status, customer_instance):
        
        booking_instance.status = booking_status
        booking_instance.updated_by = customer_instance.id
        booking_instance.customer = customer_instance
        booking_instance.updated_by_user = 'customer'
        booking_instance.save()
        
        return booking_instance


    @staticmethod
    @transaction.atomic
    def delete_booking(booking_instance):

        try:
            # Lock the row so no one else can update until commit
            booking = Booking.objects.select_for_update().get(
                id=booking_instance.id,
                status=0
            )
        except Booking.DoesNotExist:
            return None  # already assigned

        booking_instance.delete_booking() ## call delete booking_method
        return True
            


    @staticmethod
    def admin_rider_booking_history(rider_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated rider booking history with optional search query."""

        bookings = Booking.objects.filter(rider_id=rider_id).order_by(sort_by)

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

            bookings = bookings.filter(query_filter).distinct()

        paginator = Paginator(bookings, page_size)
        page = paginator.get_page(page_number)

        serialized_bookings = BookingSerializer(
            page.object_list, many=True
        ).data

        return {
            "bookings": serialized_bookings,
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
    def admin_customer_booking_history(customer_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve paginated customer booking history with optional search query."""

        bookings = Booking.objects.filter(customer_id=customer_id).order_by(sort_by)

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

            bookings = bookings.filter(query_filter).distinct()

        paginator = Paginator(bookings, page_size)
        page = paginator.get_page(page_number)

        serialized_bookings = BookingSerializer(
            page.object_list, many=True
        ).data

        return {
            "bookings": serialized_bookings,
            "total_pages": paginator.num_pages,
            "current_page": page_number,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
            "next_page": page.next_page_number() if page.has_next() else None,
            "previous_page": (
                page.previous_page_number() if page.has_previous() else None
            ),
        }