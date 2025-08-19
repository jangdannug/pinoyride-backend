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

    ## Get rider booking history
    def get_rider_booking_history(self, rider_id):
        """List all rider booking history"""
        return self.booking.get_rider_booking_history(rider_id = rider_id)

    ## Get customer booking history
    def get_customer_booking_history(self, customer_id):
        """List all customer booking history"""
        return self.booking.get_customer_booking_history(customer_id = customer_id)

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

    ## Get booking by customer and id
    def get_booking_by_customer_and_id(self,customer_id, booking_id):
        """Fetch booking"""
        booking = self.booking.get_by_customer_and_id(customer_id=customer_id, booking_id=booking_id)
        
        if booking is None:
            raise NotFoundError("Booking not found")
        return booking

    ## Accept booking
    @transaction.atomic
    def accept_booking(self, booking, rider):
        """Accept booking"""

        accept_booking = self.booking.accept_booking(booking_instance=booking, rider_instance=rider)
        if accept_booking is None:
            raise NotFoundError("Booking already assigned")

        return accept_booking


    ## Update booking status for rider
    @transaction.atomic
    def update_booking_status_for_rider(self, booking, booking_status, rider):
        """Update booking status for rider"""

        update_booking = self.booking.update_booking_status_for_rider(booking_instance=booking, booking_status=booking_status, rider_instance=rider)
    
        return update_booking


    ## Update booking status for customer
    @transaction.atomic
    def update_booking_status_for_customer(self, booking, booking_status, customer):
        """Update booking status for customer"""

        update_booking = self.booking.update_booking_status_for_customer(booking_instance=booking, booking_status=booking_status, customer_instance=customer)
    
        return update_booking


    ## Delete Booking
    @transaction.atomic
    def delete_booking(self, booking):
        """Delete booking"""

        delete_booking = self.booking.delete_booking(booking_instance=booking)
        if delete_booking is None:
            raise NotFoundError("Booking not found")
    
        return delete_booking