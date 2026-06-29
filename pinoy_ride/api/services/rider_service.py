from django.db import transaction
from api.repositories import RiderRepository
from api.models.rider_model import Rider
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
from geopy.geocoders import Nominatim
import logging

logger = logging.getLogger('myapp')
from api.utils.app_logger import app_logger

class RiderService:
    
    def __init__(self):
        self.rider = RiderRepository()
    
    ## Save rider
    @transaction.atomic
    def save_rider(self, personal_details):
        """Save rider"""
        
        new_rider = self.rider.create(rider=personal_details)

        return new_rider

    
    ## Check rider by mobile_no
    def check_mobile_no(self, rider_details):
        """Check rider"""
        
        rider = self.rider.check_rider_by_mobile(rider=rider_details)

        if rider is None:
            raise NotFoundError("Rider not found")

        return rider


     ## Check rider by mobile_no
    def login_mobile_no(self, rider_details):
        """Check rider"""
        
        rider = self.rider.check_rider_by_mobile_kyc(rider=rider_details)

        if rider is None:
            raise NotFoundError("Rider not found")

        return rider


     ## Get rider by id
    def get_rider_by_id(self,rider_id):
        """Fetch rider"""
        rider = self.rider.get_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider


    ## Get available rider
    def get_available_rider(self,rider_id):
        """Get available rider"""
        rider = self.rider.get_available_rider(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found or not available")
        return rider

    ## Update rider details
    @transaction.atomic
    def update_rider_details(self, rider_instance, personal_details):
        """Update rider details"""
        
        rider_details = self.rider.update_rider_details(rider_instance=rider_instance, personal_details=personal_details)
    
        return rider_details
    
    ## Update rider current coordinates
    @transaction.atomic
    def update_rider_coordinates(self, rider_instance, rider_lat, rider_long, current_location=None):
        """Update rider coordinates and location with reverse geocoding"""

        # Perform reverse geocoding to get location name if not provided
        if not current_location:
            try:
                geolocator = Nominatim(user_agent="pinoy_ride_app")
                location = geolocator.reverse(
                    f"{rider_lat}, {rider_long}",
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

        rider_coordinates = self.rider.update_rider_coordinates(
            rider_instance=rider_instance,
            rider_lat=rider_lat,
            rider_long=rider_long,
            current_location=current_location
        )

        return rider_coordinates


    ## Update rider available status
    @transaction.atomic
    def update_rider_available_status(self, rider_instance, status):
        """Update rider available status"""
        
        rider_avail_status = self.rider.update_rider_available_status(rider_instance=rider_instance, status=status)

        return rider_avail_status

    ## Update rider online status
    @transaction.atomic
    def update_rider_online_status(self, rider_instance, status):
        """Update rider online status"""
        
        rider_online_status = self.rider.update_rider_online_status(rider_instance=rider_instance, status=status)

        return rider_online_status


    ## Update rider auto accept status
    @transaction.atomic
    def update_auto_accept(self, rider_instance, status):
        """Update rider auto accept status"""

        rider_auto_accept = self.rider.update_auto_accept(rider_instance=rider_instance, status=status)

        return rider_auto_accept


    ## Update firebase token
    @transaction.atomic
    def update_firebase_token(self, rider_instance, firebase_token):
        """Update rider firebase token"""

        updated_rider = self.rider.update_firebase_token(
            rider_instance=rider_instance,
            firebase_token=firebase_token
        )

        return updated_rider


    ## Get rider service details
    def get_service_details(self, rider_id):
        """Get rider service details including acceptance rate, ratings, and cancellation rate"""

        # First verify rider exists
        self.get_rider_by_id(rider_id=rider_id)

        service_details = self.rider.get_rider_service_details(rider_id=rider_id)

        return service_details


    ## Record ignored booking
    @transaction.atomic
    def ignore_booking(self, rider_id, booking_id):
        """Record when a rider ignores a booking"""

        # Verify rider exists
        self.get_rider_by_id(rider_id=rider_id)

        ignored_booking = self.rider.save_ignored_booking(
            rider_id=rider_id,
            booking_id=booking_id
        )

        return ignored_booking


    ## Bulk load riders
    @transaction.atomic
    def bulk_load_riders(self, riders_data, batch_size=100):
        """
        Bulk load riders from array of objects.
        Processes in batches to handle large datasets efficiently.

        Each object should contain: first_name, mobile_no, drivers_license_no,
        plate_number, v_brand, v_model, v_color
        """
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
            'total_processed': 0,
            'total_created': 0,
            'total_skipped': 0,
            'total_failed': 0
        }

        # Import vehicle repo once
        from api.repositories import RiderVehicleDetailsRepository
        rider_vehicle_repo = RiderVehicleDetailsRepository()

        # Helper function to normalize mobile number
        def normalize_mobile_number(mobile_no: str) -> str:
            """
            Normalize mobile number to format: 63 + last 10 digits
            Examples:
            - 09171234567 -> 639171234567
            - +639171234567 -> 639171234567
            - 639171234567 -> 639171234567
            """
            # Remove all non-numeric characters
            digits_only = ''.join(c for c in mobile_no if c.isdigit())

            # Get last 10 digits
            last_10_digits = digits_only[-10:] if len(digits_only) >= 10 else digits_only

            # Prepend 63 (Philippines country code)
            return '63' + last_10_digits

        # Pre-fetch all existing mobile numbers for faster duplicate checking
        all_mobiles = set(
            Rider.objects.filter(
                application_status=1,
                status=1
            ).values_list('mobile_no', flat=True)
        )

        for rider_data in riders_data:
            results['total_processed'] += 1

            try:
                # Extract required fields
                first_name = rider_data.get('first_name', '').strip()
                mobile_no = rider_data.get('mobile_no', '').strip()
                drivers_license_no = rider_data.get('drivers_license_no', '').strip()
                plate_number = rider_data.get('plate_number', '').strip()
                v_brand = rider_data.get('brand', rider_data.get('v_brand', '')).strip()
                v_model = rider_data.get('model', rider_data.get('v_model', '')).strip()
                v_color = rider_data.get('color', rider_data.get('v_color', '')).strip()

                # Validate required fields
                if not first_name:
                    results['failed'].append({
                        'row': results['total_processed'],
                        'data': rider_data,
                        'error': 'first_name is required'
                    })
                    results['total_failed'] += 1
                    logger.warning(f"Row {results['total_processed']}: first_name is required")
                    continue

                if not mobile_no:
                    results['failed'].append({
                        'row': results['total_processed'],
                        'data': rider_data,
                        'error': 'mobile_no is required'
                    })
                    results['total_failed'] += 1
                    logger.warning(f"Row {results['total_processed']}: mobile_no is required")
                    continue

                # Normalize mobile number (get last 10 digits + prepend 63)
                original_mobile = mobile_no
                mobile_no = normalize_mobile_number(mobile_no)

                if len(mobile_no) < 12:
                    results['failed'].append({
                        'row': results['total_processed'],
                        'data': rider_data,
                        'error': f'Invalid mobile number: {original_mobile} (normalized to {mobile_no}, but must be at least 12 digits)',
                        'original_mobile': original_mobile,
                        'normalized_mobile': mobile_no
                    })
                    results['total_failed'] += 1
                    logger.warning(f"Row {results['total_processed']}: Invalid mobile number: {original_mobile}")
                    continue

                # Check if rider already exists (using pre-fetched mobile numbers)
                if mobile_no in all_mobiles:
                    # Get the actual rider for the ID
                    existing_rider = Rider.objects.filter(
                        mobile_no=mobile_no,
                        application_status=1,
                        status=1
                    ).first()

                    results['skipped'].append({
                        'row': results['total_processed'],
                        'original_mobile': original_mobile,
                        'mobile_no': mobile_no,
                        'reason': f'Rider already exists with ID: {existing_rider.id if existing_rider else "N/A"}'
                    })
                    results['total_skipped'] += 1
                    logger.info(f"Row {results['total_processed']}: Skipping existing rider: {original_mobile} (normalized: {mobile_no})")
                    continue

                # Prepare rider details
                personal_details = {
                    'first_name': first_name,
                    'middle_name': rider_data.get('middle_name', ''),
                    'last_name': rider_data.get('last_name', ''),
                    'mobile_no': mobile_no,
                    'drivers_license_no': drivers_license_no,
                    'ekyc_request_user_id': '',  # Empty for bulk load
                    'application_status': 1,
                    'status': 1,
                    'is_success_kyc': 1
                }

                # Create rider
                new_rider = self.save_rider(personal_details=personal_details)

                # Add to pre-fetched set for subsequent duplicate checks
                all_mobiles.add(mobile_no)

                # Create vehicle details if provided
                logger.info(f"Row {results['total_processed']}: Checking vehicle details - plate_number={plate_number}, v_brand={v_brand}, v_model={v_model}, v_color={v_color}")

                if plate_number or v_brand or v_model or v_color:

                    vehicle_details = {
                        'rider_id': new_rider.id,
                        'plate_number': plate_number,
                        'brand': v_brand,      # Repository expects 'brand', not 'v_brand'
                        'model': v_model,       # Repository expects 'model', not 'v_model'
                        'color': v_color,       # Repository expects 'color', not 'v_color'
                        'type': 1     # Default vehicle type = motorcycle
                    }

                    # Log response status
                    app_logger(1, "Rider Data", {
                        "rider_data": vehicle_details
                    })

                    logger.info(f"Row {results['total_processed']}: Creating vehicle details: {vehicle_details}")

                    rider_vehicle_repo.create(
                        rider_instance=new_rider,
                        rider_vehicle_details=vehicle_details
                    )
                else:
                    logger.warning(f"Row {results['total_processed']}: No vehicle details provided, skipping vehicle creation")

                results['success'].append({
                    'row': results['total_processed'],
                    'rider_id': new_rider.id,
                    'original_mobile': original_mobile,
                    'mobile_no': mobile_no,
                    'first_name': first_name
                })
                results['total_created'] += 1
                logger.info(f"Row {results['total_processed']}: Created rider: {original_mobile} (normalized: {mobile_no}) with ID: {new_rider.id}")

            except Exception as e:
                results['failed'].append({
                    'row': results['total_processed'],
                    'data': rider_data,
                    'error': str(e)
                })
                results['total_failed'] += 1
                logger.error(f"Row {results['total_processed']}: Failed to create rider - Error: {str(e)}")

        return results
