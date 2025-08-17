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

    
    ## Check rider by mobile_no
    def check_mobile_no(self, rider_details):
        """Check rider"""
        
        rider = self.rider.check_rider_by_mobile(rider=rider_details)

        if rider is None:
            raise NotFoundError("Rider not found")

        return rider


     ## Get rider by id
    def get_rider_by_id(self,rider_id):
        """Fetch rider"""
        rider = self.rider.get_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider
