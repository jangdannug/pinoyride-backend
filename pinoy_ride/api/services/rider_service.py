from django.db import transaction
from api.repositories import RiderRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class RiderService:
    
    def __init__(self):
        self.rider = RiderRepository()
    
    ## Save rider
    @transaction.atomic
    def save_rider(self, personal_details):
        """Save rider"""
        
        new_rider = self.rider.create(rider=personal_details)

        return new_rider