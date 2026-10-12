from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.utils.custom_error import ValidationError
from api.utils.vehicle_plate_utils import pretty_vehicle_type
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
            v_plate_number=rider_vehicle_details.get("plate_number", ""),
            status=rider_vehicle_details.get("status", 1),
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

        or_cr_img = rider_vehicle_details.get("or_cr_img")
        vehicle_img = rider_vehicle_details.get("vehicle_img")
        if or_cr_img:
            rider_vehicle_instance.v_or_cr_img = or_cr_img
        if vehicle_img:
            rider_vehicle_instance.v_vehicle_img = vehicle_img

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

    @staticmethod
    def list_for_rider(rider_id):
        return RiderVehicleDetails.objects.filter(rider_id=rider_id).order_by('id')

    @staticmethod
    def get_by_id_for_rider(vehicle_id, rider_id):
        try:
            return RiderVehicleDetails.objects.get(id=vehicle_id, rider_id=rider_id)
        except RiderVehicleDetails.DoesNotExist:
            return None

    @staticmethod
    def _vehicles_for_rider_qs(rider_id, lock=False):
        qs = RiderVehicleDetails.objects.filter(rider_id=rider_id)
        if lock:
            qs = qs.select_for_update()
        return qs

    @staticmethod
    def has_any_vehicle(rider_id):
        return RiderVehicleDetails.objects.filter(rider_id=rider_id).exists()

    @staticmethod
    def resolve_booking_vehicle(rider_id, booking_type=None, lock=False):
        qs = RiderVehicleDetailsRepository._vehicles_for_rider_qs(rider_id, lock=lock)
        current = qs.filter(is_current=True).first()
        if current is not None:
            return current

        if booking_type is not None and str(booking_type).strip() != "":
            matches = list(qs.filter(v_type=str(booking_type)))
            if len(matches) == 1:
                return matches[0]

        return None

    @staticmethod
    def require_booking_vehicle(rider_id, booking_type=None, lock=False):
        vehicle = RiderVehicleDetailsRepository.resolve_booking_vehicle(
            rider_id=rider_id, booking_type=booking_type, lock=lock
        )
        if vehicle is not None:
            return vehicle
        if not RiderVehicleDetailsRepository.has_any_vehicle(rider_id):
            raise ValidationError("Add a vehicle first")
        raise ValidationError(
            "Set your current vehicle in My Vehicles before going online"
        )

    @staticmethod
    def ensure_vehicle_matches_booking_type(vehicle, booking_type):
        if str(vehicle.v_type) != str(booking_type):
            needed = pretty_vehicle_type(booking_type)
            current = pretty_vehicle_type(vehicle.v_type)
            raise ValidationError(
                f"This booking needs a {needed}. Your current vehicle is a {current}."
            )

    @staticmethod
    def apply_vehicle_snapshot_to_booking(booking, vehicle):
        booking.rider_vehicle = vehicle
        booking.vehicle_plate_number = vehicle.v_plate_number
        booking.vehicle_brand = vehicle.v_brand
        booking.vehicle_model = vehicle.v_model
        booking.vehicle_color = vehicle.v_color
        booking.vehicle_type = str(vehicle.v_type) if vehicle.v_type is not None else None