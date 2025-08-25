from django.db import transaction
from api.repositories import BookingRatingsRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class BookingRatingsService:
    
    def __init__(self):
        self.booking_ratings = BookingRatingsRepository()
    
    ## Save booking ratings
    @transaction.atomic
    def save_booking_ratings(self, booking_instance, booking_ratings):
        """Save booking ratings"""
        
        new_booking_ratings = self.booking_ratings.create(booking_instance = booking_instance, booking_ratings=booking_ratings)

        return new_booking_ratings