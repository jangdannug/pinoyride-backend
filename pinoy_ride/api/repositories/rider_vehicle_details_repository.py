from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.rider_vehicle_details_model import RiderVehicleDetails

class RiderVehicleDetailsRepository:
    
    @staticmethod
    def create(rider_instance, rider_vehicle_details):
        rider_vehicle = RiderVehicleDetails.objects.create(
            rider=rider_instance,
            v_type=rider_vehicle_details.get("type", ""),
            v_brand=rider_vehicle_details.get("brand", ""),
            v_model=rider_vehicle_details.get("model", ""),
            v_color=rider_vehicle_details.get("color", ""),
            v_plate_number=rider_vehicle_details.get("plate_number", "")
        )

        rider_vehicle.v_or_cr_img = rider_vehicle_details.get("or_cr_img", "")
        rider_vehicle.v_motorcyle_img = rider_vehicle_details.get("motorcyle_img", "")

        rider_vehicle.save()
        return rider_vehicle
    
    def update(self, rider_vehicle_instance, rider_vehicle_details):

        rider_vehicle_instance.v_type = rider_vehicle_details.get("type", "")
        rider_vehicle_instance.v_brand = rider_vehicle_details.get("brand", "")
        rider_vehicle_instance.v_model = rider_vehicle_details.get("model", "")
        rider_vehicle_instance.v_color = rider_vehicle_details.get("color", "")
        rider_vehicle_instance.v_plate_number = rider_vehicle_details.get("plate_number", "")

        rider_vehicle_instance.v_or_cr_img = rider_vehicle_details.get("or_cr_img", "")
        rider_vehicle_instance.v_motorcyle_img = rider_vehicle_details.get("motorcyle_img", "")
        

        rider_vehicle_instance.save()
        return rider_vehicle_instance


    @staticmethod
    def get_vehicle_details_rider_by_id(rider_id):
        """Get rider vehicle details by rider id"""
        try:
            return RiderVehicleDetails.objects.get(rider_id=rider_id)
        except RiderVehicleDetails.DoesNotExist:
            return None