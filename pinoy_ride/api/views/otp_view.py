from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.serializers import GenerateOtpSerializer, VerifyOtpSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from api.services import (
    OtpService
)

class OtpViewSet(viewsets.ViewSet):
    """Otp Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = OtpService()


    @action(detail=False, methods=['post'], url_path='generate')
    def generate_otp(self, request):
        """Generate OTP"""
        
        try:

            # Validation
            generate_otp_serializer = GenerateOtpSerializer(data=request.data)
            if not generate_otp_serializer.is_valid():
                return AppResponse.send_error(message=generate_otp_serializer.errors, code=400)


            with transaction.atomic():
                
                otp_data = self.service.generate_otp(request.data)

           
            return AppResponse.send_success(data=otp_data, message="Record saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)




    @action(detail=False, methods=['post'], url_path='verify')
    def verify_otp(self, request):
        """Verify OTP"""
        
        try:

            # Validation
            verify_otp_serializer = VerifyOtpSerializer(data=request.data)
            if not verify_otp_serializer.is_valid():
                return AppResponse.send_error(message=verify_otp_serializer.errors, code=400)


            with transaction.atomic():
                
                otp_data = self.service.verify_otp(request.data)

           
            return AppResponse.send_success(data=[], message="OTP verified!")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


