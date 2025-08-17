from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.serializers import BookingSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from api.services import (
    BookingService,
    CustomerService,
    RiderService,
    ApiService,
    BookingPaymentService
)
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

class BookingViewSet(viewsets.ViewSet):
    """Booking Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = BookingService()
        self.customer_service = CustomerService()
        self.rider_service = RiderService()
        self.api_service = ApiService()
        self.booking_payment_service = BookingPaymentService()


    @action(detail=False, methods=['post'], url_path='create')
    def create_booking(self, request):
        """Create Booking"""
        
        try:            
            
            customer_id = request.data.get("customer_id", "")
            payment_details = json.loads(request.data.get("payment_details", "{}") or "{}")

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)

            if not payment_details:
                return AppResponse.send_error(message="Payment details is required", code=400)


            pickup_lat = request.data.get("pickup_lat", "")
            pickup_long = request.data.get("pickup_long", "")
            dropoff_lat = request.data.get("dropoff_lat", "")
            dropoff_long= request.data.get("dropoff_long", "")

            # Validation
            booking_details = {
                "pickup_location" : request.data.get("pickup_location", ""),
                "pickup_lat" : pickup_lat,
                "pickup_long" : pickup_long,
                "dropoff_location" : request.data.get("dropoff_location", ""),
                "dropoff_lat" : dropoff_lat,
                "dropoff_long" : dropoff_long,
                "payment_type" : request.data.get("payment_type", ""),
                "customer_id" : customer_id
            }

            booking_serializer = BookingSerializer(data=booking_details)

            if not booking_serializer.is_valid():
                return AppResponse.send_error(message=booking_serializer.errors, code=400)

            with transaction.atomic():
                
                customer_details = self.customer_service.get_customer_by_id(customer_id=customer_id)

                # pickup
                pickup = (pickup_lat, pickup_long)   # (lat, lng)
                # dropoff
                dropoff = (dropoff_lat, dropoff_long)

                # compute distance in kilometers
                distance_km = geodesic(pickup, dropoff).kilometers
                booking_details['distance_km'] = round(distance_km, 2)

                # save booking
                booking_details = self.service.save_booking(customer_instance = customer_details, booking_details=booking_details)

                # save booking payment
                self.booking_payment_service.save_booking_payment(booking_instance=booking_details, booking_payment=payment_details) 

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    

    @action(detail=False, methods=['post'], url_path='search_location')
    def search_location(self, request):
        """Search Location"""
        
        try:            
            
            location_search_key = request.data.get("location_search_key", "")
            if not location_search_key:
                return AppResponse.send_error(message="Location Search key is required", code=400)

            geolocator = Nominatim(user_agent="booking_app_2025")

            locations = geolocator.geocode(
                            location_search_key,
                            exactly_one=False,
                            limit=5,
                            country_codes="ph",
                            timeout=10
                        )
            results = []
            if locations:
                for loc in locations:
                    results.append({
                        "name": loc.address,
                        "lat": loc.latitude,
                        "long": loc.longitude
                    })

            # request_data = {
            #                     "name": "Apple MacBook Pro 16",
            #                     "data": {
            #                         "year": 2019,
            #                         "price": 1849.99,
            #                         "CPU model": "Intel Core i9",
            #                         "Hard disk size": "1 TB"
            #                     }
            #                 }


            # results = self.api_service.post_request("https://api.restful-api.dev/objects", request_data)

            return AppResponse.send_success(data=results, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='get_pending')
    def get_pending(self, request):
        """Get Pending Bookings"""
        
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
                
                self.rider_service.get_rider_by_id(rider_id=rider_id)

                booking_details = self.service.get_pending(rider_lat=rider_lat, rider_long=rider_long)
           
            return AppResponse.send_success(data=booking_details, message="Bookings fetched successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    
    @action(detail=False, methods=['post'], url_path='get_details')
    def get_details(self, request):
        """Get Booking details"""
        
        try:            
            
            booking_id = request.data.get("booking_id", "")

            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)

            booking_details = self.service.get_booking_by_id(booking_id=booking_id)

            serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking details fetched successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    
    @action(detail=False, methods=['post'], url_path='update_status_for_rider')
    def update_status_for_rider(self, request):
        """Update status for rider"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            booking_id = request.data.get("booking_id", "")
            rider_lat = request.data.get("current_lat", "")
            rider_long = request.data.get("current_long", "")
            status = request.data.get("status", "")
            allowed_status = ["1", "2", "3"]

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)
            if not rider_lat:
                return AppResponse.send_error(message="Current lat is required", code=400)
            if not rider_long:
                return AppResponse.send_error(message="Current long is required", code=400)
            if status not in allowed_status:
                return AppResponse.send_error(message="Invalid status "+str(status), code=400)

            with transaction.atomic():
                booking_details = self.service.get_booking_by_id(booking_id=booking_id)
                rider_details = self.rider_service.get_rider_by_id(rider_id=rider_id)
                
                ## validate booking record if it is linked to rider_id
                if status != "1":
                    self.service.get_booking_by_rider_and_id(rider_id=rider_id, booking_id=booking_id)

                self.service.update_booking_status_for_rider(booking=booking_details, booking_status = status, rider=rider_details)

                # refresh booking_details
                booking_details.refresh_from_db()

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking details fetched successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)

