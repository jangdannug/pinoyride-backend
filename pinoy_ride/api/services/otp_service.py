from django.db import transaction
from api.repositories import OtpRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class OtpService:
    
    def __init__(self):
        self.otp = OtpRepository()
    
    ## Generate OTP
    @transaction.atomic
    def generate_otp(self, user_details):
        """Generate OTP"""
        
        otp_code = self.otp.generate(user_details=user_details)

        return otp_code


    ## Verify OTP
    @transaction.atomic
    def verify_otp(self, otp_data):
        """Verify OTP"""
        
        otp_record = self.otp.check_if_exists(otp_data=otp_data)
        
        if otp_record is None:
            raise ValidationError("Invalid OTP")

        if otp_record.is_expired():
            raise ValidationError("OTP expired")

        return otp_record