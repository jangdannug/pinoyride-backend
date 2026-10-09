from django.db import transaction
from api.repositories import RiderVehicleDetailsRepository, RiderRepository
from api.models import Booking, RiderVehicleDetails
from api.utils.custom_error import NotFoundError, ValidationError
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
    
     ## Save rider vehicle details
    @transaction.atomic
    def update_rider_vehicle(self, rider_id, vehicle_type, rider_vehicle_details):
        """Update rider vehicle"""
        
        rider_instance = self.get_rider_by_id(rider_id = rider_id)

        rider_vehicle_instance = self.rider_vehicle_details_repository.get_vehicle_details_rider_by_id_and_type(rider_id=rider_id, vehicle_type=vehicle_type)

        
        if rider_vehicle_instance is None:
            # create rider vehicle details
            self.rider_vehicle_details_repository.create(rider_instance=rider_instance, rider_vehicle_details=rider_vehicle_details)
        else:
            #update rider vehicle details
            self.rider_vehicle_details_repository.update(rider_vehicle_instance = rider_vehicle_instance, rider_vehicle_details = rider_vehicle_details)

        return rider_vehicle_details

    ## Get rider by id
    def get_rider_by_id(self,rider_id):
        """Get rider by id"""
        rider = self.rider_repository.get_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider

    def vehicle_used_in_completed_transactions(self, vehicle):
        if not vehicle or not vehicle.rider_id or not vehicle.v_type:
            return False
        return Booking.objects.filter(
            rider_id=vehicle.rider_id,
            status=3,
            deleted_at__isnull=True,
            booking_type=str(vehicle.v_type),
        ).exists()

    @transaction.atomic
    def add_vehicle(self, rider_id, rider_vehicle_details):
        rider_instance = self.get_rider_by_id(rider_id=rider_id)
        rider_vehicle_details = {**rider_vehicle_details, "status": 1}
        return self.rider_vehicle_details_repository.create(
            rider_instance=rider_instance,
            rider_vehicle_details=rider_vehicle_details,
        )

    @transaction.atomic
    def update_vehicle_by_id(self, rider_id, vehicle_id, rider_vehicle_details):
        vehicle = self.rider_vehicle_details_repository.get_by_id_for_rider(
            vehicle_id=vehicle_id, rider_id=rider_id
        )
        if vehicle is None:
            raise NotFoundError("Vehicle not found")
        return self.rider_vehicle_details_repository.update(
            rider_vehicle_instance=vehicle,
            rider_vehicle_details=rider_vehicle_details,
        )

    @transaction.atomic
    def delete_vehicle(self, rider_id, vehicle_id):
        vehicle = self.rider_vehicle_details_repository.get_by_id_for_rider(
            vehicle_id=vehicle_id, rider_id=rider_id
        )
        if vehicle is None:
            raise NotFoundError("Vehicle not found")
        if self.vehicle_used_in_completed_transactions(vehicle):
            raise ValidationError(
                "This vehicle cannot be deleted because it was used in completed trips."
            )
        if vehicle.is_current:
            vehicle.is_current = False
            vehicle.save(update_fields=["is_current", "updated_at"])
        vehicle.delete()
        return True

    @transaction.atomic
    def set_current_vehicle(self, rider_id, vehicle_id):
        vehicle = self.rider_vehicle_details_repository.get_by_id_for_rider(
            vehicle_id=vehicle_id, rider_id=rider_id
        )
        if vehicle is None:
            raise NotFoundError("Vehicle not found")
        RiderVehicleDetails.objects.filter(
            rider_id=rider_id, is_current=True
        ).exclude(id=vehicle_id).update(is_current=False)
        vehicle.is_current = True
        vehicle.save(update_fields=["is_current", "updated_at"])
        return vehicle