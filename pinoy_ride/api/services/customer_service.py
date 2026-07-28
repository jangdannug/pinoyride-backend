from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError, ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
from geopy.geocoders import Nominatim
import base64
class CustomerService:
    
    def __init__(self):
        self.customer = CustomerRepository()
    
    ## Save customer
    @transaction.atomic
    def save_customer(self, customer_details):
        """Save customer"""
        
        new_customer = self.customer.create(customer=customer_details)

        return new_customer



    ## Check customer by mobile_no
    def check_mobile_no(self, customer_details):
        """Check customer"""
        
        customer = self.customer.check_customer_by_mobile(customer=customer_details)

        if customer is None:
            raise NotFoundError("Customer not found")

        return customer

    ## Check customer by mobile_no
    def login_mobile_no(self, customer_details):
        """Check customer"""
        
        customer = self.customer.check_customer_by_mobile_kyc(customer=customer_details)

        if customer is None:
            raise NotFoundError("User not found")

        return customer
    
    ## Get customer by id
    def get_customer_by_id(self,customer_id):
        """Fetch customer"""
        customer = self.customer.get_customer_by_id(customer_id=customer_id)

        if customer is None:
            raise NotFoundError("Customer "+ str(customer_id) + " not found")
        return customer


    ## Update firebase token
    @transaction.atomic
    def update_firebase_token(self, customer_instance, firebase_token):
        """Update customer firebase token"""

        updated_customer = self.customer.update_firebase_token(
            customer_instance=customer_instance,
            firebase_token=firebase_token
        )

        return updated_customer


    ## Update customer login status
    @transaction.atomic
    def update_login_status(self, customer_instance, status):
        """Update customer login status"""

        updated_customer = self.customer.update_login_status(
            customer_instance=customer_instance,
            status=status
        )

        return updated_customer

    ## Update customer coordinates
    @transaction.atomic
    def update_customer_coordinates(self, customer_instance, customer_lat, customer_long, current_location=None):
        """Update customer coordinates and location with reverse geocoding"""

        # Perform reverse geocoding to get location name if not provided
        if not current_location:
            try:
                geolocator = Nominatim(user_agent="pinoy_ride_app")
                location = geolocator.reverse(
                    f"{customer_lat}, {customer_long}",
                    exactly_one=True,
                    timeout=5
                )
                if location:
                    # Extract street, barangay, city, and province
                    raw_address = location.raw.get('address', {})

                    location_parts = []

                    # 1. Street/Road name
                    if 'road' in raw_address:
                        location_parts.append(raw_address['road'])
                    elif 'street' in raw_address:
                        location_parts.append(raw_address['street'])

                    # 2. Barangay (suburb/village/neighbourhood/city_district)
                    if 'suburb' in raw_address:
                        location_parts.append(raw_address['suburb'])
                    elif 'village' in raw_address:
                        location_parts.append(raw_address['village'])
                    elif 'neighbourhood' in raw_address:
                        location_parts.append(raw_address['neighbourhood'])
                    elif 'city_district' in raw_address:
                        location_parts.append(raw_address['city_district'])

                    # 3. City
                    if 'city' in raw_address:
                        city = raw_address['city']
                        # Clean up city names (remove "City of" prefix)
                        if city.startswith('City of '):
                            city = city.replace('City of ', '')
                        location_parts.append(city)
                    elif 'town' in raw_address:
                        location_parts.append(raw_address['town'])
                    elif 'municipality' in raw_address:
                        location_parts.append(raw_address['municipality'])

                    # 4. Province/County
                    if 'county' in raw_address:
                        county = raw_address['county']
                        # Avoid duplication (e.g., if city is "Manila" and county is "Manila")
                        if county not in ' '.join(location_parts):
                            location_parts.append(county)
                    elif 'state' in raw_address:
                        # For Metro Manila and similar regions
                        state = raw_address['state']
                        if state not in ' '.join(location_parts):
                            location_parts.append(state)

                    if location_parts:
                        current_location = ', '.join(location_parts)
            except Exception:
                # If geocoding fails, continue without location name
                pass

        updated_customer = self.customer.update_coordinates(
            customer_instance=customer_instance,
            customer_lat=customer_lat,
            customer_long=customer_long,
            current_location=current_location
        )

        return updated_customer