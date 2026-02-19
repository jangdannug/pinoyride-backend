from django.db import transaction
from api.repositories import BookingIssuesRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class BookingIssuesService:
    
    def __init__(self):
        self.booking_issues = BookingIssuesRepository()
    
    ## Save booking issues
    @transaction.atomic
    def save_booking_issues(self, booking_instance, booking_issues):
        """Save booking issues"""
        
        new_booking_issues = self.booking_issues.create(booking_instance = booking_instance, booking_issues=booking_issues)

        return new_booking_issues