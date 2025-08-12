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
