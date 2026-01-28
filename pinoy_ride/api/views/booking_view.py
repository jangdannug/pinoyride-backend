from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
import json
from api.serializers import BookingSerializer, PromoSerializer
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from api.services import (
    BookingService,
    CustomerService,
    RiderService,
    BookingPaymentService,
    BookingRatingsService,
    WalletService,
    PromoService,
    PromoAvailedService
)
from api.base import (
    ApiService
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
        self.booking_ratings_service = BookingRatingsService()
        self.wallet_service = WalletService()
        self.promo_service = PromoService()
        self.promo_availed_service = PromoAvailedService()


    @action(detail=False, methods=['post'], url_path='inquire')
    def inquire_booking(self, request):
        """Return booking details"""

        try:
            customer_id = request.data.get("customer_id", "")
            booking_type = request.data.get("booking_type", "1")
            promo_id = request.data.get("promo_id", "")
            if not customer_id:
                    return AppResponse.send_error(message="Customer id is required", code=400)

            self.customer_service.get_customer_by_id(customer_id=customer_id)

            pickup_lat = request.data.get("pickup_lat", "")
            pickup_long = request.data.get("pickup_long", "")
            dropoff_lat = request.data.get("dropoff_lat", "")
            dropoff_long= request.data.get("dropoff_long", "")

            # origin
            origin = (pickup_lat, pickup_long)   # (lat, lng)
            # destination
            destination = (dropoff_lat, dropoff_long)

            # compute distance in kilometers
            distance_km = geodesic(origin, destination).kilometers
            distance_km_round = round(distance_km, 2)

            if booking_type == '1':
                # Booking Type = 1 - Motorcyle
                minimum_fare = 50.00
                pesos_per_km = 10
                booking_fee = 10
                commission_prcentage = .20 #20%

            elif booking_type == '2':
                # Booking Type = 2 - Car - 4 Seaters
                minimum_fare = 100.00
                pesos_per_km = 10
                booking_fee = 10
                commission_prcentage = .20 #20%

            elif booking_type == '3':
                # Booking Type = 3 = Car - 6 Seaters
                minimum_fare = 120.00
                pesos_per_km = 10
                booking_fee = 10
                commission_prcentage = .20 #20%

            base_amount = distance_km_round * pesos_per_km
            total_amount_wo_promo = minimum_fare + base_amount + booking_fee
            total_amount = minimum_fare + base_amount + booking_fee

            commision = round(total_amount * commission_prcentage, 2)
            rider_net_amount = round(total_amount - commision, 2)

            ## Check promo AND check the total amount if greater than 150
            promo_discount_percentage = 0
            promo_discount = 0
            if promo_id and total_amount >= 150:
                promo_details = self.promo_service.get_promo_by_id(promo_id=promo_id)
                validate_promo = self.promo_service.validate_promo(promo_id=promo_id, customer_id=customer_id)
                if promo_details:
                    if promo_details.code == 'RIDE93333':

                        promo_discount_percentage = .08 #8% Discount if total amount > 150
                        if total_amount >= 200: 
                            promo_discount_percentage = .10 #10% Discount if total amount > 200

                        promo_discount = round(total_amount * promo_discount_percentage, 2)

                        # Change commission and total amount
                        total_amount = round(total_amount - promo_discount, 2)
                        commision = round(total_amount - rider_net_amount, 2)

            response = {
                "distance_km_round" : distance_km_round,
                "minimum_fare" : minimum_fare,
                "pesos_per_km" : pesos_per_km,
                "base_amount" : round(base_amount,2),
                "booking_fee" : booking_fee,
                "promo_discount" : promo_discount,
                "commission" : commision,
                "rider_net_amount" : rider_net_amount,
                "total_amount_wo_promo" : round(total_amount_wo_promo,2),
                "total_amount" : round(total_amount,2),
                "pretty_total_amount_wo_promo" : f"{total_amount_wo_promo:,.2f}",
                "pretty_total_amount" : f"{total_amount:,.2f}"
            }

            return AppResponse.send_success(data=response, message="Success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



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
            payment_type = request.data.get("payment_type", "")
            payment_total_amount = payment_details.get("total_amount", 0)
            promo_id = request.data.get("promo_id", "")
            

            ## Valiate promo
            if promo_id:
                promo_details = self.promo_service.get_promo_by_id(promo_id=promo_id)
                self.promo_service.validate_promo(promo_id=promo_id, customer_id=customer_id)

            # Validation
            booking_details = {
                "booking_type" : request.data.get("booking_type", ""),
                "pickup_location" : request.data.get("pickup_location", ""),
                "pickup_lat" : pickup_lat,
                "pickup_long" : pickup_long,
                "dropoff_location" : request.data.get("dropoff_location", ""),
                "dropoff_lat" : dropoff_lat,
                "dropoff_long" : dropoff_long,
                "payment_type" : request.data.get("payment_type", ""),
                "note_to_rider" : request.data.get("note_to_rider", ""),
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

                # check customer's wallet
                if payment_type == 'wallet':
                    self.wallet_service.check_balance(user_id = customer_id, user_type='customer', amount=payment_total_amount)

                # save booking
                booking_details = self.service.save_booking(customer_instance = customer_details, booking_details=booking_details)

                # save booking payment
                self.booking_payment_service.save_booking_payment(booking_instance=booking_details, booking_payment=payment_details) 

                # save promo availed
                if promo_id:
                    self.promo_availed_service.save_promo_availed(promo_instance=promo_details, customer_instance=customer_details, booking_instance=booking_details)

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='add_tip')
    def add_tip(self, request):
        """Add tip"""
        
        try:            
            customer_id = request.data.get("customer_id", "")
            booking_id = request.data.get("booking_id", "")
            tip = request.data.get("tip", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)
            if not tip:
                return AppResponse.send_error(message="Tip is required", code=400)


            with transaction.atomic():
                
                self.customer_service.get_customer_by_id(customer_id=customer_id)

                booking_details = self.service.get_booking_by_customer_and_id(customer_id=customer_id, booking_id=booking_id)
                booking_payment_instance = booking_details.booking_payment.first()

                self.booking_payment_service.add_tip(booking_payment_instance=booking_payment_instance, tip=tip)
                    
                serializer = BookingSerializer(booking_details)

            return AppResponse.send_success(data=serializer.data, message="Tip added successfully")


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
            # if not location_search_key:
            #     return AppResponse.send_error(message="Location Search key is required", code=400)

            # geolocator = Nominatim(user_agent="booking_app_2025")

            # locations = geolocator.geocode(
            #                 location_search_key,
            #                 exactly_one=False,
            #                 limit=5,
            #                 country_codes="ph",
            #                 timeout=10
            #             )
            # results = []
            # if locations:
            #     for loc in locations:
            #         results.append({
            #             "name": loc.address,
            #             "lat": loc.latitude,
            #             "long": loc.longitude
            #         })

            api_key = 'AIzaSyAlpSoXuJzvo8uR1qbdtbbbk1sx4MHKIQk'
            url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            params = {
                "input": location_search_key,
                "components": "country:PH",
                "key": api_key
            }
            res = self.api_service.get_request(url=url, params=params)

            results = []
            for prediction in res.get("predictions", []):
                place_id = prediction["place_id"]

                # Get details for each suggestion
                details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                params = {"place_id": place_id, "key": api_key}
                details_res = res = self.api_service.get_request(url=details_url, params=params)

                if "result" in details_res:
                    loc = details_res["result"]["geometry"]["location"]
                    results.append({
                        "description": prediction["description"],  # user-friendly address
                        "address": details_res["result"].get("formatted_address"),
                        "lat": loc["lat"],
                        "long": loc["lng"],
                        "place_id": place_id
                    })

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
            booking_type = request.data.get("booking_type", "1")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not rider_lat:
                return AppResponse.send_error(message="Current lat is required", code=400)
            if not rider_long:
                return AppResponse.send_error(message="Current long is required", code=400)

            with transaction.atomic():
                
                rider_details = self.rider_service.get_rider_by_id(rider_id=rider_id)

                self.rider_service.update_rider_coordinates(rider_instance=rider_details, rider_lat=rider_lat, rider_long=rider_long)

                booking_details = self.service.get_pending(rider_lat=rider_lat, rider_long=rider_long, booking_type=booking_type)
           
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


    @action(detail=False, methods=['post'], url_path='get_history')
    def get_history(self, request):
        """Get Booking History"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            customer_id = request.data.get("customer_id", "")
            user_type = request.data.get("user_type", "")

            if not user_type:
                return AppResponse.send_error(message="User type is required", code=400)

            if user_type == 'rider':
                if not rider_id:
                    return AppResponse.send_error(message="Rider id is required", code=400)
            elif user_type == 'customer':
                if not customer_id:
                    return AppResponse.send_error(message="Customer id is required", code=400)
            else:
                return AppResponse.send_error(message="Invalid user type", code=400)
            
            with transaction.atomic():

                if user_type == 'customer':
                     
                    self.customer_service.get_customer_by_id(customer_id=customer_id)
                    booking_details = self.service.get_customer_booking_history(customer_id=customer_id)
                    return AppResponse.send_success(data=booking_details, message="Bookings fetched successfully")

                elif user_type == 'rider':

                    self.rider_service.get_rider_by_id(rider_id=rider_id)
                    booking_details = self.service.get_rider_booking_history(rider_id=rider_id)
                    return AppResponse.send_success(data=booking_details, message="Bookings fetched successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='accept_booking')
    def accept_booking(self, request):
        """Accept booking"""
        
        try:            
            
            rider_id = request.data.get("rider_id", "")
            booking_id = request.data.get("booking_id", "")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)

            with transaction.atomic():
                booking_details = self.service.get_booking_by_id(booking_id=booking_id)
                rider_details = self.rider_service.get_available_rider(rider_id=rider_id)
                

                self.service.accept_booking(booking=booking_details, rider=rider_details)

                ## update rider status to unavailable
                self.rider_service.update_rider_available_status(rider_instance=rider_details, status=2)

                # refresh booking_details
                booking_details.refresh_from_db()

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking accepted")


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
            allowed_status = ["2", "3"]

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
                
                if booking_details.status == 3:
                    return AppResponse.send_error(message="Booking is already completed", code=400)
            
                ## validate booking record if it is linked to rider_id
                if status != "1":
                    self.service.get_booking_by_rider_and_id(rider_id=rider_id, booking_id=booking_id)

                if status == "3": #if status == completed update rider status to available and credit amount to wallet
                    if booking_details.payment_type == 'wallet':
                        self.wallet_service.update_booking_wallets(booking_details=booking_details)

                    self.rider_service.update_rider_available_status(rider_instance=rider_details, status=1)

                    #check if booking has promo
                    promo_availed_details = self.promo_availed_service.get_promo_availed_by_booking_id(booking_id=booking_id)
                    if promo_availed_details:
                        # Update promo availed status to completed
                        self.promo_availed_service.update_promo_availed_status(promo_availed_instance = promo_availed_details, status=1)

                self.service.update_booking_status_for_rider(booking=booking_details, booking_status = status, rider=rider_details)
                self.rider_service.update_rider_coordinates(rider_instance=rider_details, rider_lat=rider_lat, rider_long=rider_long)

                # refresh booking_details
                booking_details.refresh_from_db()

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking updated successfully ")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    
    @action(detail=False, methods=['post'], url_path='update_status_for_customer')
    def update_status_for_customer(self, request):
        """Update status for customer"""
        
        try:            
            
            customer_id = request.data.get("customer_id", "")
            booking_id = request.data.get("booking_id", "")
            status = request.data.get("status", "")
            allowed_status = ["4"]

            if not customer_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)
            if status not in allowed_status:
                return AppResponse.send_error(message="Invalid status "+str(status), code=400)

            with transaction.atomic():
                booking_details = self.service.get_booking_by_id(booking_id=booking_id)
                customer_details = self.customer_service.get_customer_by_id(customer_id=customer_id)
                
                ## validate booking record if it is linked to customer_id
                self.service.get_booking_by_customer_and_id(customer_id=customer_id, booking_id=booking_id)

                self.service.update_booking_status_for_customer(booking=booking_details, booking_status = status, customer=customer_details)

                if status == "4": #if status == cancelled update rider status to available
                    if booking_details.rider_id:
                        rider_details = self.rider_service.get_rider_by_id(rider_id=booking_details.rider_id)
                        self.rider_service.update_rider_available_status(rider_instance=rider_details, status=1)

                    #check if booking has promo
                    promo_availed_details = self.promo_availed_service.get_promo_availed_by_booking_id(booking_id=booking_id)
                    if promo_availed_details:
                        # Update promo availed status to cancelled
                        self.promo_availed_service.update_promo_availed_status(promo_availed_instance = promo_availed_details, status=2)

                # refresh booking_details
                booking_details.refresh_from_db()

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking updated successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)

    @action(detail=False, methods=['post'], url_path='get_promo_list')
    def get_promo_list(self, request):
        """Get Promo List"""
        
        try:            
            customer_id = request.data.get("customer_id", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)

            promos = self.promo_service.get_promo_list(
                customer_id=customer_id
            )

            return AppResponse.send_success(
                data=promos, message="Promos listed successfully", code=200
            )
    

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
        

    @action(detail=False, methods=['post'], url_path='check_promo_code')
    def check_promo_code(self, request):
        """Check Promo Code"""
        
        try:            
            customer_id = request.data.get("customer_id", "")
            promo_code = request.data.get("promo_code", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)
            if not promo_code:
                return AppResponse.send_error(message="Promo code is required", code=400)

            with transaction.atomic():
                promo_details = self.promo_service.get_promo_by_code(promo_code=promo_code, customer_id=customer_id)

                serializer = PromoSerializer(promo_details)
        
            return AppResponse.send_success(data=serializer.data, message="Promo details")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='rate')
    def rate(self, request):
        """Rate Booking"""
        
        try:            
            customer_id = request.data.get("customer_id", "")
            booking_id = request.data.get("booking_id", "")
            rate = request.data.get("rate", "")

            if not customer_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)
            if not rate:
                return AppResponse.send_error(message="Rate is required", code=400)

            with transaction.atomic():
                booking_details = self.service.get_booking_by_id(booking_id=booking_id)

                ## validate booking record if it is linked to customer_id
                self.service.get_booking_by_customer_and_id(customer_id=customer_id, booking_id=booking_id)

                booking_ratings = {
                    "rate" : rate,
                    "compliment" : request.data.get("compliment", ""),
                }

                self.booking_ratings_service.save_booking_ratings(booking_instance=booking_details, booking_ratings=booking_ratings)

                serializer = BookingSerializer(booking_details)
           
            return AppResponse.send_success(data=serializer.data, message="Booking rate saved successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    @action(detail=False, methods=['post'], url_path='delete')
    def delete_booking(self, request):
        """Delete booking"""
        
        try:            
            
            booking_id = request.data.get("booking_id", "")

            if not booking_id:
                return AppResponse.send_error(message="Booking id is required", code=400)

            with transaction.atomic():
                booking_details = self.service.get_booking_by_id(booking_id=booking_id)
                
                # validate status if != pending
                if booking_details.status != 0:
                    return AppResponse.send_error(message="Booking not found", code=404)

                self.service.delete_booking(booking=booking_details)
           
            return AppResponse.send_success(data=[], message="Booking deleted successfully")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='auto_book')
    def auto_book(self, request):
        """Auto Book"""
        
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
                
                rider_details = self.rider_service.get_rider_by_id(rider_id=rider_id)

                self.rider_service.update_rider_coordinates(rider_instance=rider_details, rider_lat=rider_lat, rider_long=rider_long)

                # get random pending booking
                pending_booking = self.service.get_random_pending(rider_lat=rider_lat, rider_long=rider_long)

                response = {}
                if pending_booking:
                    booking_details = self.service.get_booking_by_id(booking_id=pending_booking['id'])

                    # accept booking
                    self.service.accept_booking(booking=booking_details, rider=rider_details)

                    booking_details.refresh_from_db()

                    response = BookingSerializer(booking_details).data
                else:
                    return AppResponse.send_error(message="No pending bookings available", code=404)

            return AppResponse.send_success(data=response, message="Booking accepted")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
