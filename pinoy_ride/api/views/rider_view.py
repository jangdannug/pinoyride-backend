from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.services import (
    RiderService,
    RiderVehicleDetailsService,
    OtpService
)
from api.serializers import RiderSerializer, RiderVehicleDetailsSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction

class RiderViewSet(viewsets.ViewSet):
    """Riders Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = RiderService()
        self.rider_vehicle_service = RiderVehicleDetailsService()
        self.otp_service = OtpService()


    @action(detail=False, methods=['post'], url_path='apply')
    def rider_application(self, request):
        """Rider application"""
        
        try:

            personal_details = json.loads(request.data.get("personal_details", "{}"))
            vehicle_details = json.loads(request.data.get("vehicle_details", "{}"))
            
            drivers_license_img= request.data.get("drivers_license_img", None)
            personal_details['drivers_license_img'] = drivers_license_img

            or_cr_img= request.data.get("or_cr_img", None)
            motorcyle_img= request.data.get("motorcyle_img", None)
            vehicle_details['or_cr_img'] = or_cr_img
            vehicle_details['motorcyle_img'] = motorcyle_img

            # Validation
            rider_serializer = RiderSerializer(data=personal_details)
            if not rider_serializer.is_valid():
                return AppResponse.send_error(message=rider_serializer.errors, code=400)

            rider_vehicle_serializer = RiderVehicleDetailsSerializer(data=vehicle_details)
            if not rider_vehicle_serializer.is_valid():
                return AppResponse.send_error(message=rider_vehicle_serializer.errors, code=400)

            with transaction.atomic():
                
                rider_details = self.service.save_rider(personal_details=personal_details)

                rider_vehicle = self.rider_vehicle_service.save_rider_vehicle(rider_id = rider_details.id , rider_vehicle_details=vehicle_details)

                serializer = RiderSerializer(rider_details)
           
            return AppResponse.send_success(data=serializer.data, message="Record saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """Rider login"""
        
        try:

            mobile_no = request.data.get("mobile_no", "")
            otp_code = request.data.get("otp_code", "")

            if not mobile_no:
                return AppResponse.send_error(message="Mobile number is required", code=400)

            response_data = []
            rider = self.service.check_mobile_no(request.data)
            otp_data = {
                "user_type" : "rider",
                "mobile_no" : mobile_no
            }

            if not otp_code:
                self.otp_service.generate_otp(user_details = otp_data)

                response_data = {
                    "is_otp" : "1"
                 }
            else:
                otp_data['code'] = otp_code

                self.otp_service.verify_otp(otp_data = otp_data)
                serializer = RiderSerializer(rider)
                response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Login success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)