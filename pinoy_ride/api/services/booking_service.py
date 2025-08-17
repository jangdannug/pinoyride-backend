from django.db import transaction
from api.repositories import BookingRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class BookingService:
    
    def __init__(self):
        self.booking = BookingRepository()
    
    ## Save booking
    @transaction.atomic
    def save_booking(self, customer_instance, booking_details):
        """Save booking"""
        
        new_booking = self.booking.create(customer_instance = customer_instance, booking_details=booking_details)

        return new_booking

    ## Get pending bookings
    def get_pending(self, rider_lat, rider_long):
        """List all pending bookings"""
        return self.booking.pending_list(rider_lat = rider_lat, rider_long=rider_long)


     ## Get booking by id
    def get_booking_by_id(self,booking_id):
        """Fetch booking"""
        booking = self.booking.get_by_id(booking_id=booking_id)
        
        if booking is None:
            raise NotFoundError("Booking "+ str(booking_id) + " not found")
        return booking

    ## Get booking by rider and id
    def get_booking_by_rider_and_id(self,rider_id, booking_id):
        """Fetch booking"""
        booking = self.booking.get_by_rider_and_id(rider_id=rider_id, booking_id=booking_id)
        
        if booking is None:
            raise NotFoundError("Booking not found")
        return booking


    ## Update booking status for rider
    @transaction.atomic
    def update_booking_status_for_rider(self, booking, booking_status, rider):
        """Update booking status for rider"""

        update_booking = self.booking.update_booking_status_for_rider(booking_instance=booking, booking_status=booking_status, rider_instance=rider)
    
        return update_booking