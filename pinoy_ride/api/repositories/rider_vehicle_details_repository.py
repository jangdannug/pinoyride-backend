from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.rider_vehicle_details_model import RiderVehicleDetails
import logging

logger = logging.getLogger('myapp')

class RiderVehicleDetailsRepository:
    
    @staticmethod
    def create(rider_instance, rider_vehicle_details):
        """Create rider vehicle details"""
        brand = rider_vehicle_details.get("brand", "")
        model = rider_vehicle_details.get("model", "")
        color = rider_vehicle_details.get("color", "")

        logger.info(f"Creating vehicle details for rider {rider_instance.id}: brand={brand}, model={model}, color={color}")

        rider_vehicle = RiderVehicleDetails.objects.create(
            rider=rider_instance,
            v_type=rider_vehicle_details.get("type", ""),
            v_brand=brand,
            v_model=model,
            v_color=color,
            v_plate_number=rider_vehicle_details.get("plate_number", "")
        )

        rider_vehicle.v_or_cr_img = rider_vehicle_details.get("or_cr_img", "")
        rider_vehicle.v_vehicle_img = rider_vehicle_details.get("vehicle_img", "")

        rider_vehicle.save()

        logger.info(f"Vehicle details created with ID {rider_vehicle.id}: v_brand={rider_vehicle.v_brand}, v_model={rider_vehicle.v_model}, v_color={rider_vehicle.v_color}")
        return rider_vehicle
    
    def update(self, rider_vehicle_instance, rider_vehicle_details):

        rider_vehicle_instance.v_type = rider_vehicle_details.get("type", "")
        rider_vehicle_instance.v_brand = rider_vehicle_details.get("brand", "")
        rider_vehicle_instance.v_model = rider_vehicle_details.get("model", "")
        rider_vehicle_instance.v_color = rider_vehicle_details.get("color", "")
        rider_vehicle_instance.v_plate_number = rider_vehicle_details.get("plate_number", "")

        rider_vehicle_instance.v_or_cr_img = rider_vehicle_details.get("or_cr_img", "")
        rider_vehicle_instance.v_vehicle_img = rider_vehicle_details.get("vehicle_img", "")
        

        rider_vehicle_instance.save()
        return rider_vehicle_instance


    @staticmethod
    def get_vehicle_details_rider_by_id(rider_id):
        """Get rider vehicle details by rider id"""
        try:
            return RiderVehicleDetails.objects.get(rider_id=rider_id)
        except RiderVehicleDetails.DoesNotExist:
            return None
        
    @staticmethod
    def get_vehicle_details_rider_by_id_and_type(rider_id, vehicle_type):
        """Get rider vehicle details by rider id and vehicle type"""
        try:
            return RiderVehicleDetails.objects.get(rider_id=rider_id, v_type = vehicle_type)
        except RiderVehicleDetails.DoesNotExist:
            return None