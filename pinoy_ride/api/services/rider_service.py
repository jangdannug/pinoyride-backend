from django.db import transaction
from api.repositories import RiderRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
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
    def update_rider_coordinates(self, rider_instance, rider_lat, rider_long):
        """Update rider available status"""
        
        rider_coordinates = self.rider.update_rider_coordinates(rider_instance=rider_instance, rider_lat=rider_lat, rider_long=rider_long)

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
