from django.db import transaction
from api.repositories import RiderRepository, BookingRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
class AdminRiderService:
    
    def __init__(self):
        self.rider = RiderRepository()
        self.booking = BookingRepository()

    ## Admin get list of applicants
    def admin_list_applicants(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all rider applicants with pagination"""
        return self.rider.admin_rider_applicants(page_number, page_size, search_query, filters, sort_by)


    ## Get rider applicant by id
    def get_rider_applicant_by_id(self,rider_id):
        """Fetch rider"""
        rider = self.rider.get_applicant_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider


    ## Update rider applicant status
    @transaction.atomic
    def update_rider_applicant_status(self, rider, applicant_status, auth_user_id):
        """Update rider applicant status"""

        update_rider = self.rider.update_rider_applicant_status(rider_instance=rider, applicant_status=applicant_status, auth_user_id=auth_user_id)
    
        return update_rider

    
    ## Admin get list of riders
    def admin_list_riders(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all riders with pagination"""
        return self.rider.admin_riders_list(page_number, page_size, search_query, filters, sort_by)


    ## Get rider by id
    def get_rider_by_id(self,rider_id):
        """Fetch rider"""
        rider = self.rider.get_by_id(rider_id=rider_id)
        
        if rider is None:
            raise NotFoundError("Rider "+ str(rider_id) + " not found")
        return rider


    ## Update rider status
    @transaction.atomic
    def update_rider_status(self, rider, rider_status, auth_user_id):
        """Update rider status"""

        update_rider = self.rider.update_rider_status(rider_instance=rider, rider_status=rider_status, auth_user_id=auth_user_id)
    
        return update_rider

    
    ## Admin get list of rider booking history
    def admin_list_rider_booking_history(self, rider_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all rider booking history with pagination"""
        return self.booking.admin_rider_booking_history(rider_id, page_number, page_size, search_query, filters, sort_by)



    ## Delete rider
    @transaction.atomic
    def delete_rider(self, rider, auth_user_id):
        """Delete rider"""

        delete_rider = self.rider.delete_rider(rider_instance=rider, auth_user_id=auth_user_id)
    
        return delete_rider