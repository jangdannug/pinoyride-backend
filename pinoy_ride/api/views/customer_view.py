from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.services import (
    CustomerService
)
from api.serializers import CustomerSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction

class CustomerViewSet(viewsets.ViewSet):
    """Customers Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = CustomerService()
        # self.rider_vehicle_service = RiderVehicleDetailsService()


    @action(detail=False, methods=['post'], url_path='sign_up')
    def sign_up(self, request):
        """Customer sign up"""
        
        try:

            # Validation
            customer_details = {
                "fname" : request.data.get("fname", ""),
                "mname" : request.data.get("mname", ""),
                "lname" : request.data.get("lname", ""),
                "mobile" : request.data.get("mobile", ""),
                "email" : request.data.get("email", ""),
                "customer_type" : "1"
            }

            customer_serializer = CustomerSerializer(data=customer_details)
            if not customer_serializer.is_valid():
                return AppResponse.send_error(message=customer_serializer.errors, code=400)

            with transaction.atomic():
                
                customer_details = self.service.save_customer(customer_details=customer_details)


                serializer = CustomerSerializer(customer_details)
           
            return AppResponse.send_success(data=serializer.data, message="Record saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
