from django.db import transaction
from api.repositories import BookingPaymentRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class BookingPaymentService:
    
    def __init__(self):
        self.booking_payment = BookingPaymentRepository()
    
    ## Save booking payment
    @transaction.atomic
    def save_booking_payment(self, booking_instance, booking_payment):
        """Save booking payment"""
        
        new_booking_payment = self.booking_payment.create(booking_instance = booking_instance, booking_payment=booking_payment)

        return new_booking_payment

    ## Save booking payment by booking_id
    def get_record_by_booking_id(self, booking_id):
        """Get booking payment by booking_id"""
        
        booking_payment = self.booking_payment.get_by_id(booking_id=booking_id)
        
        if booking_payment is None:
            raise NotFoundError("Booking not found")
        return booking_payment

    ## Add tip
    @transaction.atomic
    def add_tip(self, booking_payment_instance, tip):
        """Add tip"""

        update_booking_payment = self.booking_payment.add_tip(booking_payment_instance=booking_payment_instance, tip=tip)
    
        return update_booking_payment