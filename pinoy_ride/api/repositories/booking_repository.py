from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.booking_model import Booking
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger

class BookingRepository:
    
    @staticmethod
    @transaction.atomic
    def create(customer_instance, booking_details):
        new_booking = Booking.objects.create(
            customer=customer_instance,
            pickup_location=booking_details.get("pickup_location", ""),
            dropoff_location=booking_details.get("dropoff_location", ""),
            pickup_lat=booking_details.get("pickup_lat", ""),
            pickup_long=booking_details.get("pickup_long", ""),
            dropoff_lat=booking_details.get("dropoff_lat", ""),
            dropoff_long=booking_details.get("dropoff_long", ""),
            distance_km=booking_details.get("distance_km", ""),
            payment_type=booking_details.get("payment_type", ""),
        )

        new_booking.save()
        return new_booking


    

    @staticmethod
    def pending_list(rider_lat, rider_long):
        """Retrieve list of pending bookings"""
        rider_current_latlong = (rider_lat, rider_long)
        radius_km = 1.5 #0.5 -> 500 meters #3 -> 3000 meters radius

        bookings = Booking.objects.filter(status=0)  # pending only

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
    def get_by_id(booking_id):
        """Get booking by id"""
        try:
            return Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return None
