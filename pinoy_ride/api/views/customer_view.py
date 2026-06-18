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
from api.repositories import (
    BookingRepository,
    RiderRepository
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
        self.booking_repository = BookingRepository()
        self.rider_repository = RiderRepository()


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
            firebase_token = request.data.get("firebase_token", None)

            if not mobile_no:
                return AppResponse.send_error(message="Mobile number is required", code=400)

            response_data = []

            with transaction.atomic():
                customer = self.service.login_mobile_no(request.data)

                ekyc_request_user_id = customer.ekyc_request_user_id

                # Check if record exist on ekyc user details table
                self.ekyc_service.check_topph_user_details(ekyc_request_user_id=ekyc_request_user_id)
                # disable check ekyc details
                # if check_user_details is None:
                    # self.ekyc_service.get_topph_user_details(ref_id=ekyc_request_user_id)

                # create wallet if not exist
                self.wallet_service.create_customer_wallet(customer_id=customer.id)

                # Update firebase_token if provided
                if firebase_token:
                    self.service.update_firebase_token(customer_instance=customer, firebase_token=firebase_token)

            serializer = CustomerSerializer(customer)
            response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Login success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
    

    @action(detail=False, methods=['post'], url_path='get_customer_details')
    def get_customer_details(self, request):
        """Customer details"""
        
        try:

            customer_id = request.data.get("customer_id", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer Id is required", code=400)

            response_data = []

            with transaction.atomic():
                customer = self.service.get_customer_by_id(customer_id=customer_id)

            serializer = CustomerSerializer(customer)
            response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Customer details")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='get_rider_location')
    def get_rider_location(self, request):
        """Get rider's current location for a booking"""

        try:

            customer_id = request.data.get("customer_id", "")
            booking_id = request.data.get("booking_id", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer Id is required", code=400)

            if not booking_id:
                return AppResponse.send_error(message="Booking Id is required", code=400)

            with transaction.atomic():
                # Verify the booking belongs to the customer
                booking = self.booking_repository.get_by_customer_and_id(
                    customer_id=customer_id,
                    booking_id=booking_id
                )

                if not booking:
                    return AppResponse.send_error(message="Booking not found", code=404)

                # Check if booking has a rider assigned
                if not booking.rider:
                    return AppResponse.send_error(message="No rider assigned to this booking", code=404)

                # Get rider details
                rider = booking.rider

                response_data = {
                    "rider_id": rider.id,
                    "current_lat": rider.current_lat,
                    "current_long": rider.current_long,
                    "current_location": rider.current_location
                }

            return AppResponse.send_success(data=response_data, message="Rider location retrieved successfully")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='update_current_location')
    def update_current_location(self, request):
        """Update current location"""

        try:

            customer_id = request.data.get("customer_id", "")
            current_lat = request.data.get("current_lat", "")
            current_long = request.data.get("current_long", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)
            if not current_lat:
                return AppResponse.send_error(message="Current lat is required", code=400)
            if not current_long:
                return AppResponse.send_error(message="Current long is required", code=400)

            with transaction.atomic():
                customer_details = self.service.get_customer_by_id(customer_id=customer_id)

                # Service layer handles reverse geocoding automatically
                self.service.update_customer_coordinates(
                    customer_instance=customer_details,
                    customer_lat=current_lat,
                    customer_long=current_long
                )

                serializer = CustomerSerializer(customer_details)

            return AppResponse.send_success(data=serializer.data, message="Customer location updated successfully")


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
        
    
    @action(
        detail=False, methods=["post"], url_path="get_wallet_history"
    )
    def get_wallet_history(self, request):
        """List customer wallet history with pagination and search query"""
        try:
            page = int(request.data.get("page", 1))
            perpage = int(request.data.get("perpage", 10))
            query = request.data.get("query", None)
            sort_by = request.data.get("sort_by")
            name_filter = request.data.get("name_filter")
            customer_id = request.data.get("customer_id", "")

            filters = {}

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            wallet_history = self.wallet_service.get_wallet_history(
                user_id=customer_id, user_type='customer',  page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=wallet_history, message="Customer's wallet history listed successfully"
            )
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)