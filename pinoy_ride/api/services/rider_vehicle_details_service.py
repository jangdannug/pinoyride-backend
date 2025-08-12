from django.db import transaction
from api.repositories import RiderVehicleDetailsRepository, RiderRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class RiderVehicleDetailsService:
    
    def __init__(self):
        self.rider_vehicle_details_repository = RiderVehicleDetailsRepository()
        self.rider_repository = RiderRepository()
    
    ## Save rider vehicle details
    @transaction.atomic
    def save_rider_vehicle(self, rider_id, rider_vehicle_details):
        """Save rider vehicle"""
          
        rider_instance = self.get_rider_by_id(rider_id = rider_id)
        
        new_rider_vehicle = self.rider_vehicle_details_repository.create(rider_instance = rider_instance, rider_vehicle_details = rider_vehicle_details)

        return new_rider_vehicle


    ## Get rider by id
    def get_rider_by_id(self,rider_id):
        """Get rider by id"""
        rider = self.rider_repository.get_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider