from django.db import transaction
from api.repositories import RiderAddressRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class RiderAddressService:
    
    def __init__(self):
        self.rider_address = RiderAddressRepository()
    
    ## Save rider address
    @transaction.atomic
    def save_rider_address(self, rider_instance, rider_address):
        """Save rider address"""
        
        new_rider_address = self.rider_address.create(rider_instance = rider_instance, rider_address=rider_address)

        return new_rider_address
