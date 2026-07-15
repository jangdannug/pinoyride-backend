from django.db import transaction
from api.repositories import RiderRepository, BookingRepository, RiderVehicleDetailsRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.services import BookingIssuesService
class AdminRiderService:

    def __init__(self):
        self.rider = RiderRepository()
        self.booking = BookingRepository()
        self.booking_issues = BookingIssuesService()
        self.rider_vehicle = RiderVehicleDetailsRepository()

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


    ## Get rider current location
    def get_rider_current_location(self, rider_id):
        """Get rider current location"""

        rider = self.get_rider_by_id(rider_id=rider_id)

        return {
            'rider_id': rider.id,
            'rider_code': rider.code,
            'first_name': rider.first_name,
            'last_name': rider.last_name,
            'current_location': rider.current_location,
            'current_lat': rider.current_lat,
            'current_long': rider.current_long,
        }


    ## Get all complaints
    def get_all_complaints(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-created_at"):
        """Get all complaints with pagination"""
        return self.booking_issues.get_all_complaints(
            page_number=page_number,
            page_size=page_size,
            search_query=search_query,
            filters=filters,
            sort_by=sort_by
        )


    ## Upload rider images
    @transaction.atomic
    def upload_rider_images(self, rider_id, drivers_license_img=None, v_vehicle_img=None, v_or_cr_img=None):
        """Upload and save rider images"""

        # Get rider
        rider = self.get_rider_by_id(rider_id)

        uploaded_images = {}

        # Upload and save driver's license image to rider table
        if drivers_license_img:
            rider.drivers_license_img = drivers_license_img
            rider.save()
            # Return the relative path
            if rider.drivers_license_img and hasattr(rider.drivers_license_img, 'name'):
                uploaded_images['drivers_license_img'] = rider.drivers_license_img.name

        # Upload and save vehicle images to rider_vehicle_details table
        if v_vehicle_img or v_or_cr_img:
            # Get existing vehicle details for this rider
            vehicle_details = self.rider_vehicle.get_vehicle_details_rider_by_id_and_type(rider_id, 1)

            if vehicle_details is None:
                raise ValidationError("Vehicle details not found for this rider. Please create vehicle details first.")

            # Update only the image fields, retain other existing values
            if v_vehicle_img:
                vehicle_details.v_vehicle_img = v_vehicle_img
            if v_or_cr_img:
                vehicle_details.v_or_cr_img = v_or_cr_img
            vehicle_details.save()

            # Return the relative paths
            if v_vehicle_img and hasattr(vehicle_details, 'v_vehicle_img') and vehicle_details.v_vehicle_img:
                uploaded_images['v_vehicle_img'] = vehicle_details.v_vehicle_img.name
            if v_or_cr_img and hasattr(vehicle_details, 'v_or_cr_img') and vehicle_details.v_or_cr_img:
                uploaded_images['v_or_cr_img'] = vehicle_details.v_or_cr_img.name

        return uploaded_images