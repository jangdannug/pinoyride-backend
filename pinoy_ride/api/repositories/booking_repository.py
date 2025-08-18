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
            booking_type=booking_details.get("booking_type", ""),
            dropoff_location=booking_details.get("dropoff_location", ""),
            pickup_lat=booking_details.get("pickup_lat", ""),
            pickup_long=booking_details.get("pickup_long", ""),
            dropoff_lat=booking_details.get("dropoff_lat", ""),
            dropoff_long=booking_details.get("dropoff_long", ""),
            distance_km=booking_details.get("distance_km", ""),
            payment_type=booking_details.get("payment_type", ""),
            note_to_rider=booking_details.get("note_to_rider", ""),
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
    def update_booking_status_for_rider(booking_instance, booking_status, rider_instance):
        
        booking_instance.status = booking_status
        booking_instance.updated_by = rider_instance.id
        booking_instance.rider_id = rider_instance
        booking_instance.save()
        
        return booking_instance

    
    @staticmethod
    @transaction.atomic
    def update_booking_status_for_customer(booking_instance, booking_status, customer_instance):
        
        booking_instance.status = booking_status
        booking_instance.updated_by = customer_instance.id
        booking_instance.customer = customer_instance
        booking_instance.save()
        
        return booking_instance