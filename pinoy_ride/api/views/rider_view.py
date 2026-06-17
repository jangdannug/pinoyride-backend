from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.services import (
    RiderService,
    RiderVehicleDetailsService,
    OtpService,
    RiderAddressService,
    WalletService,
    EkycApiService
)
from api.serializers import RiderSerializer, RiderVehicleDetailsSerializer, WalletSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction

class RiderViewSet(viewsets.ViewSet):
    """Riders Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = RiderService()
        self.rider_vehicle_service = RiderVehicleDetailsService()
        self.otp_service = OtpService()
        self.rider_address_service = RiderAddressService()
        self.wallet_service = WalletService()
        self.ekyc_service = EkycApiService()


    @action(detail=False, methods=['post'], url_path='apply')
    def rider_application(self, request):
        """Rider application"""
        
        try:

            personal_details = json.loads(request.data.get("personal_details", "{}"))
            vehicle_details = json.loads(request.data.get("vehicle_details", "{}"))
            rider_address = json.loads(request.data.get("rider_address", "{}") or "{}")
            
            drivers_license_img= request.data.get("drivers_license_img", None)
            personal_details['drivers_license_img'] = drivers_license_img

            or_cr_img= request.data.get("or_cr_img", None)
            vehicle_img= request.data.get("vehicle_img", None)
            vehicle_details['or_cr_img'] = or_cr_img
            vehicle_details['vehicle_img'] = vehicle_img

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

                if rider_address:
                    rider_address['type'] = '1'
                    self.rider_address_service.save_rider_address(rider_instance= rider_details, rider_address=rider_address)

                # create wallet
                wallet_details = {
                    "user_id" : rider_details.id,
                    "user_type" : "rider",
                    "type" : "user-wallet"
                }
                self.wallet_service.save_wallet(wallet_details)

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

            with transaction.atomic():
                rider = self.service.login_mobile_no(request.data)

                ekyc_request_user_id = rider.ekyc_request_user_id

                # Check if record exist on ekyc user details table
                check_user_details = self.ekyc_service.check_topph_user_details(ekyc_request_user_id=ekyc_request_user_id)
                if check_user_details is None:
                    self.ekyc_service.get_topph_user_details(ref_id=ekyc_request_user_id)

                # create wallet if not exist
                self.wallet_service.create_rider_wallet(rider_id=rider.id)

            serializer = RiderSerializer(rider)
            response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Login success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='get_rider_details')
    def get_rider_details(self, request):
        """Rider details"""
        
        try:

            rider_id = request.data.get("rider_id", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider Id is required", code=400)

            response_data = []

            with transaction.atomic():
                customer = self.service.get_rider_by_id(rider_id=rider_id)

            serializer = RiderSerializer(customer)
            response_data = serializer.data


            return AppResponse.send_success(data=response_data, message="Rider details")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    @action(detail=False, methods=['post'], url_path='update_online_status')
    def update_online_status(self, request):
        """Update online status"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            status = request.data.get("status", "")
            rider_lat = request.data.get("current_lat", "")
            rider_long = request.data.get("current_long", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not status:
                return AppResponse.send_error(message="Status is required", code=400)
            if not rider_lat:
                return AppResponse.send_error(message="Current lat is required", code=400)
            if not rider_long:
                return AppResponse.send_error(message="Current long is required", code=400)

            with transaction.atomic():
                rider_details = self.service.get_rider_by_id(rider_id=rider_id)
                
                ## update rider online status
                self.service.update_rider_online_status(rider_instance=rider_details, status=status)

                self.service.update_rider_coordinates(rider_instance=rider_details, rider_lat=rider_lat, rider_long=rider_long)

                serializer = RiderSerializer(rider_details)
           
            return AppResponse.send_success(data=serializer.data, message="Rider status updated successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='update_auto_accept')
    def update_auto_accept(self, request):
        """Update auto accept status"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            status = request.data.get("auto_accept", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not status:
                return AppResponse.send_error(message="Status is required", code=400)

            with transaction.atomic():
                rider_details = self.service.get_rider_by_id(rider_id=rider_id)
                
                ## update rider auto accept status
                self.service.update_auto_accept(rider_instance=rider_details, status=status)

                serializer = RiderSerializer(rider_details)
           
            return AppResponse.send_success(data=serializer.data, message="Rider auto accept status updated successfully")


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

            rider_id = request.data.get("rider_id", "")
            rider_lat = request.data.get("current_lat", "")
            rider_long = request.data.get("current_long", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not rider_lat:
                return AppResponse.send_error(message="Current lat is required", code=400)
            if not rider_long:
                return AppResponse.send_error(message="Current long is required", code=400)

            with transaction.atomic():
                rider_details = self.service.get_rider_by_id(rider_id=rider_id)

                # Service layer handles reverse geocoding automatically
                self.service.update_rider_coordinates(
                    rider_instance=rider_details,
                    rider_lat=rider_lat,
                    rider_long=rider_long
                )

                serializer = RiderSerializer(rider_details)

            return AppResponse.send_success(data=serializer.data, message="Rider location updated successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
        
    
    @action(detail=False, methods=['post'], url_path='documents')
    def documents_details(self, request):
        """Update details and documents"""
        
        try:

            vehicle_details = json.loads(request.data.get("vehicle_details", "{}"))
            personal_details = json.loads(request.data.get("personal_details", "{}") or "{}")
            
            rider_id= request.data.get("rider_id", "")
            drivers_license_img= request.data.get("drivers_license_img", "")

            drivers_license_img= request.data.get("drivers_license_img", None)
            personal_details['drivers_license_img'] =  drivers_license_img

            or_cr_img= request.data.get("or_cr_img", None)
            vehicle_img= request.data.get("vehicle_img", None)
            vehicle_details['or_cr_img'] = or_cr_img
            vehicle_details['vehicle_img'] = vehicle_img

            # Validation
            if not rider_id:
                return AppResponse.send_error(message="Rider ID is required", code=400)
            if not drivers_license_img:
                return AppResponse.send_error(message="Driver's license is required", code=400)
                        
            rider_vehicle_serializer = RiderVehicleDetailsSerializer(data=vehicle_details)
            if not rider_vehicle_serializer.is_valid():
                return AppResponse.send_error(message=rider_vehicle_serializer.errors, code=400)

            with transaction.atomic():
                
                rider_details = self.service.get_rider_by_id(rider_id=rider_id)

                self.service.update_rider_details(rider_instance=rider_details, personal_details=personal_details)

                self.rider_vehicle_service.update_rider_vehicle(rider_id = rider_details.id, vehicle_type = vehicle_details['type'], rider_vehicle_details=vehicle_details)

                serializer = RiderSerializer(rider_details)

                rider_details.refresh_from_db()

            return AppResponse.send_success(data=serializer.data, message="Record updated successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='top_up')
    def top_up(self, request):
        """Top up"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            amount = request.data.get("amount", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not amount:
                return AppResponse.send_error(message="Amount is required", code=400)

            with transaction.atomic():
                rider_details = self.service.get_rider_by_id(rider_id=rider_id)

                wallet_details = self.wallet_service.get_rider_wallet(rider_id=rider_id)
                
                top_up_details = {
                    "type" : "credit",
                    "credit_amount" : amount,
                    "description" : "Top-up",
                }
                wallet_details = self.wallet_service.top_up(wallet_instance = wallet_details, top_up_details = top_up_details)

                serializer = WalletSerializer(wallet_details)
           
            return AppResponse.send_success(data=serializer.data, message="Record added successfully")


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
        """List rider wallet history with pagination and search query"""
        try:
            page = int(request.data.get("page", 1))
            perpage = int(request.data.get("perpage", 10))
            query = request.data.get("query", None)
            sort_by = request.data.get("sort_by")
            name_filter = request.data.get("name_filter")
            rider_id = request.data.get("rider_id", "")

            filters = {}

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            wallet_history = self.wallet_service.get_wallet_history(
                user_id=rider_id, user_type='rider',  page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=wallet_history, message="Rider's wallet history listed successfully"
            )
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='get_service_details')
    def get_service_details(self, request):
        """Get rider service details including acceptance rate, ratings, and cancellation rate"""

        try:
            rider_id = request.data.get("rider_id", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)

            service_details = self.service.get_service_details(rider_id=rider_id)

            return AppResponse.send_success(data=service_details, message="Service details retrieved successfully")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='ignore_booking')
    def ignore_booking(self, request):
        """Record when a rider ignores a booking"""

        try:
            rider_id = request.data.get("rider_id", "")
            booking_id = request.data.get("booking_id", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)

            with transaction.atomic():
                ignored_booking = self.service.ignore_booking(
                    rider_id=rider_id,
                    booking_id=booking_id
                )

            return AppResponse.send_success(data={"ignored_booking_id": ignored_booking.id}, message="Booking ignored recorded successfully")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)