from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.services import (
    CustomerService,
    OtpService,
    CustomerAddressService,
    WalletService,
    EkycApiService
)
from api.serializers import CustomerSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction

class CustomerViewSet(viewsets.ViewSet):
    """Customers Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = CustomerService()
        self.otp_service = OtpService()
        self.customer_address_service = CustomerAddressService()
        # self.rider_vehicle_service = RiderVehicleDetailsService()
        self.wallet_service = WalletService()
        self.ekyc_service = EkycApiService()


    @action(detail=False, methods=['post'], url_path='sign_up')
    def sign_up(self, request):
        """Customer sign up"""
        
        try:

            customer_address = json.loads(request.data.get("customer_address", "{}") or "{}")

            # Validation
            customer_details = {
                "fname" : request.data.get("fname", ""),
                "mname" : request.data.get("mname", ""),
                "lname" : request.data.get("lname", ""),
                "mobile" : request.data.get("mobile", ""),
                "email" : request.data.get("email", ""),
                "login_type" : "mobile_number",
                "customer_type" : "1",
                "status" : 1
            }

            customer_serializer = CustomerSerializer(data=customer_details)
            if not customer_serializer.is_valid():
                return AppResponse.send_error(message=customer_serializer.errors, code=400)

            with transaction.atomic():
                
                customer_details = self.service.save_customer(customer_details=customer_details)

                if customer_address:
                    customer_address['type'] = '1'
                    self.customer_address_service.save_customer_address(customer_instance = customer_details, customer_address=customer_address)

                # create wallet
                wallet_details = {
                    "user_id" : customer_details.id,
                    "user_type" : "customer",
                    "type" : "user-wallet"
                }
                self.wallet_service.save_wallet(wallet_details)

                serializer = CustomerSerializer(customer_details)
           
            return AppResponse.send_success(data=serializer.data, message="Record saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)

    

    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """Customer login"""
        
        try:

            mobile_no = request.data.get("mobile_no", "")
            otp_code = request.data.get("otp_code", "")

            if not mobile_no:
                return AppResponse.send_error(message="Mobile number is required", code=400)

            response_data = []

            with transaction.atomic():
                customer = self.service.login_mobile_no(request.data)

                ekyc_request_user_id = customer.ekyc_request_user_id

                # Check if record exist on ekyc user details table
                check_user_details = self.ekyc_service.check_topph_user_details(ekyc_request_user_id=ekyc_request_user_id)
                if check_user_details is None:
                    self.ekyc_service.get_topph_user_details(ref_id=ekyc_request_user_id)

                # create wallet if not exist
                self.wallet_service.create_customer_wallet(customer_id=customer.id)
                
            serializer = CustomerSerializer(customer)
            response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Login success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    @action(detail=False, methods=['post'], url_path='save_address')
    def save_address(self, request):
        """Save customer address"""
        
        try:
            
            customer_id = request.data.get("customer_id", None)
            customer_address = json.loads(request.data.get("customer_address", "{}") or "{}")

            if not customer_id:
                return AppResponse.send_error(message="Customer Id is required", code=400)

            if not customer_address:
                return AppResponse.send_error(message="Customer Address is required", code=400)

        
            with transaction.atomic():
                
                customer_details = self.service.get_customer_by_id(customer_id=customer_id)
               
                self.customer_address_service.save_customer_address(customer_instance = customer_details, customer_address=customer_address)

                serializer = CustomerSerializer(customer_details)
           
            return AppResponse.send_success(data=serializer.data, message="Record saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)