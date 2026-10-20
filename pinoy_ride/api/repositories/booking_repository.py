from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value, Exists, OuterRef
from django.db.models.functions import Concat
from api.models.booking_model import Booking
from api.models.wallet_history_model import WalletHistory
from api.models.ignored_booking_model import IgnoredBooking
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger
import math, random
import os

def format_eta_minutes(minutes: int) -> str:
    """
    Format minutes into human-readable time string
    Examples:
        5 -> "5 mins"
        45 -> "45 mins"
        60 -> "1 hr"
        75 -> "1 hr 15 mins"
        120 -> "2 hrs"
        135 -> "2 hrs 15 mins"
    """
    if minutes <= 0:
        return "0 mins"

    if minutes < 60:
        return f"{minutes} min{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes == 0:
        return f"{hours} hr{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hr{'s' if hours != 1 else ''} {remaining_minutes} min{'s' if remaining_minutes != 1 else ''}"
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
        radius_km = float(os.getenv('RIDER_RADIUS_KM', 1.5)) #0.5 -> 500 meters #3 -> 3000 meters radius

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

        # Calculate ETAs for nearby bookings
        # Import GoogleMapsService here to avoid circular imports
        from api.services.google_maps_service import GoogleMapsService
        google_maps_service = GoogleMapsService()

        next_adv = None
        if rider_id:
            from api.services.booking_window_service import next_advance_for_rider
            next_adv = next_advance_for_rider(rider_id)

        serialized_bookings = []
        for booking in nearby_bookings:
            booking_data = BookingSerializer(booking).data

            # Calculate distance from rider to pickup
            distance_from_rider = geodesic(
                rider_current_latlong,
                (booking.pickup_lat, booking.pickup_long)
            ).kilometers
            booking_data['distance_from_rider_km'] = round(distance_from_rider, 2)

            # Get ETA from rider to pickup
            try:
                eta_to_pickup = google_maps_service.get_eta(
                    origin_lat=rider_lat,
                    origin_lng=rider_long,
                    dest_lat=float(booking.pickup_lat),
                    dest_lng=float(booking.pickup_long),
                    mode="driving"
                )
                eta_rider_to_pickup = eta_to_pickup.get('duration_in_traffic_minutes', eta_to_pickup.get('duration_minutes', 0))
                booking_data['eta_rider_to_pickup_minutes'] = eta_rider_to_pickup
                booking_data['pretty_eta_rider_to_pickup'] = format_eta_minutes(eta_rider_to_pickup)
            except Exception as e:
                app_logger(1, f"Error calculating ETA to pickup: {str(e)}", [])
                # Fallback to simple calculation
                eta_rider_to_pickup = round((distance_from_rider / 30) * 60)
                booking_data['eta_rider_to_pickup_minutes'] = eta_rider_to_pickup
                booking_data['pretty_eta_rider_to_pickup'] = format_eta_minutes(eta_rider_to_pickup)

            # Get ETA from pickup to dropoff (total trip time)
            try:
                eta_to_dropoff = google_maps_service.get_eta(
                    origin_lat=float(booking.pickup_lat),
                    origin_lng=float(booking.pickup_long),
                    dest_lat=float(booking.dropoff_lat),
                    dest_lng=float(booking.dropoff_long),
                    mode="driving"
                )
                eta_pickup_to_dropoff = eta_to_dropoff.get('duration_in_traffic_minutes', eta_to_dropoff.get('duration_minutes', 0))
                booking_data['eta_pickup_to_dropoff_minutes'] = eta_pickup_to_dropoff
                booking_data['pretty_eta_pickup_to_dropoff'] = format_eta_minutes(eta_pickup_to_dropoff)
            except Exception as e:
                app_logger(1, f"Error calculating ETA to dropoff: {str(e)}", [])
                # Fallback: calculate pickup->dropoff
                pickup_to_dropoff_distance = geodesic(
                    (booking.pickup_lat, booking.pickup_long),
                    (booking.dropoff_lat, booking.dropoff_long)
                ).kilometers
                eta_pickup_to_dropoff = round((pickup_to_dropoff_distance / 30) * 60)
                booking_data['eta_pickup_to_dropoff_minutes'] = eta_pickup_to_dropoff
                booking_data['pretty_eta_pickup_to_dropoff'] = format_eta_minutes(eta_pickup_to_dropoff)

            # Overlap plan section 5: hide rides this rider can't fit before their next advance booking
            if next_adv is not None:
                from api.services.booking_window_service import regular_fits
                try:
                    if not regular_fits(next_adv, timezone.now(), eta_rider_to_pickup, eta_pickup_to_dropoff, booking):
                        continue
                except Exception as e:
                    app_logger(1, f"Error checking advance fit: {str(e)}", [])

            serialized_bookings.append(booking_data)

        return {
            "bookings": serialized_bookings
        }


    @staticmethod
    def open_bookings_for_vehicle(vehicle_id):
        return Booking.objects.filter(
            rider_vehicle_id=vehicle_id,
            status__in=[1, 2, 5],
            deleted_at__isnull=True,
        )

    @staticmethod
    def vehicle_has_open_booking(vehicle_id):
        return BookingRepository.open_bookings_for_vehicle(vehicle_id).exists()

    @staticmethod
    def random_pending(rider_lat, rider_long, booking_type):
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
            .filter(
                status=0,
                pickup_lat__range=lat_range,
                pickup_long__range=lng_range,
                booking_type=booking_type,
            )
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

            # Add ETA calculations for the selected booking
            from api.services.google_maps_service import GoogleMapsService
            google_maps_service = GoogleMapsService()

            # Calculate distance from rider to pickup
            distance_from_rider = geodesic(
                rider_current_latlong,
                (random_booking.pickup_lat, random_booking.pickup_long)
            ).kilometers
            serialized_booking['distance_from_rider_km'] = round(distance_from_rider, 2)

            # Get ETA from rider to pickup
            try:
                eta_to_pickup = google_maps_service.get_eta(
                    origin_lat=rider_lat,
                    origin_lng=rider_long,
                    dest_lat=float(random_booking.pickup_lat),
                    dest_lng=float(random_booking.pickup_long),
                    mode="driving"
                )
                eta_rider_to_pickup = eta_to_pickup.get('duration_in_traffic_minutes', eta_to_pickup.get('duration_minutes', 0))
                serialized_booking['eta_rider_to_pickup_minutes'] = eta_rider_to_pickup
                serialized_booking['pretty_eta_rider_to_pickup'] = format_eta_minutes(eta_rider_to_pickup)
            except Exception as e:
                app_logger(1, f"Error calculating ETA to pickup: {str(e)}", [])
                eta_rider_to_pickup = round((distance_from_rider / 30) * 60)
                serialized_booking['eta_rider_to_pickup_minutes'] = eta_rider_to_pickup
                serialized_booking['pretty_eta_rider_to_pickup'] = format_eta_minutes(eta_rider_to_pickup)

            # Get ETA from pickup to dropoff (total trip time)
            try:
                eta_to_dropoff = google_maps_service.get_eta(
                    origin_lat=float(random_booking.pickup_lat),
                    origin_lng=float(random_booking.pickup_long),
                    dest_lat=float(random_booking.dropoff_lat),
                    dest_lng=float(random_booking.dropoff_long),
                    mode="driving"
                )
                eta_pickup_to_dropoff = eta_to_dropoff.get('duration_in_traffic_minutes', eta_to_dropoff.get('duration_minutes', 0))
                serialized_booking['eta_pickup_to_dropoff_minutes'] = eta_pickup_to_dropoff
                serialized_booking['pretty_eta_pickup_to_dropoff'] = format_eta_minutes(eta_pickup_to_dropoff)
            except Exception as e:
                app_logger(1, f"Error calculating ETA to dropoff: {str(e)}", [])
                pickup_to_dropoff_distance = geodesic(
                    (random_booking.pickup_lat, random_booking.pickup_long),
                    (random_booking.dropoff_lat, random_booking.dropoff_long)
                ).kilometers
                eta_pickup_to_dropoff = round((pickup_to_dropoff_distance / 30) * 60)
                serialized_booking['eta_pickup_to_dropoff_minutes'] = eta_pickup_to_dropoff
                serialized_booking['pretty_eta_pickup_to_dropoff'] = format_eta_minutes(eta_pickup_to_dropoff)

        return serialized_booking


    @staticmethod
    def get_rider_booking_history(rider_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """Retrieve rider booking history"""
        from api.models.advance_booking_rider_release_model import AdvanceBookingRiderRelease

        released_ids = set(
            AdvanceBookingRiderRelease.objects.filter(rider_id=rider_id).values_list(
                "booking_id", flat=True
            )
        )
        for bid in WalletHistory.objects.filter(
            tran_type="cancel_penalty",
            type="debit",
            wallet__user_type="rider",
            wallet__user_id=rider_id,
        ).values_list("booking_id", flat=True):
            try:
                released_ids.add(int(bid))
            except (TypeError, ValueError):
                continue

        bookings = Booking.objects.filter(
            Q(rider_id=rider_id) | Q(id__in=released_ids)
        ).distinct().order_by(sort_by)
      
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
            page.object_list,
            many=True,
            context={"history_rider_id": rider_id, "omit_contact_phone": True},
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
            page.object_list,
            many=True,
            context={"omit_contact_phone": True},
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
    def check_customer_ongoing_booking(customer_id):
        """Check if customer has ongoing bookings"""
        return Booking.objects.filter(
            customer_id=customer_id,
            status__in=[1, 2]
        ).first()
    
    @staticmethod
    def check_rider_ongoing_booking(rider_id):
        """Check if rider has ongoing bookings"""
        return Booking.objects.filter(
            rider_id=rider_id,
            status__in=[1, 2]
        ).first()
        
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
        from api.repositories.rider_vehicle_details_repository import (
            RiderVehicleDetailsRepository,
        )

        from api.services import booking_window_service as bws
        # Lock the rider first so two accepts for the same rider can't both pass the checks
        rider_locked = bws.lock_rider(rider_instance.id) or rider_instance

        try:
            # Lock the row so no one else can update until commit
            booking = Booking.objects.select_for_update().get(
                id=booking_instance.id,
                status=0,
                rider_id__isnull=True
            )
        except Booking.DoesNotExist:
            return None  # already assigned

        # Overlap plan section 5: not on another ride, and still makes the next advance pickup
        bws.check_rider_regular(rider_locked, booking)

        vehicle = RiderVehicleDetailsRepository.require_booking_vehicle(
            rider_id=rider_instance.id,
            booking_type=booking.booking_type,
            lock=True,
        )
        RiderVehicleDetailsRepository.ensure_vehicle_matches_booking_type(
            vehicle, booking.booking_type
        )
        RiderVehicleDetailsRepository.apply_vehicle_snapshot_to_booking(
            booking, vehicle
        )

        booking.status = 1
        booking.updated_by = rider_instance.id
        booking.rider = rider_instance
        booking.save()
        return booking


    @staticmethod
    @transaction.atomic
    def update_booking_status_for_rider(booking_instance, booking_status, rider_instance):
        from django.utils import timezone

        booking_instance.status = booking_status
        booking_instance.updated_by = rider_instance.id
        booking_instance.rider_id = rider_instance
        booking_instance.updated_by_user = 'rider'
        if int(booking_status) == 3 and not booking_instance.completed_at:
            booking_instance.completed_at = timezone.now()
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