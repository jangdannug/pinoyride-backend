from django.db import transaction
from api.repositories import OtpRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
from api.base import (
    ApiService
)
from django.conf import settings
import json
class OtpService:
    
    def __init__(self):
        self.otp = OtpRepository()
        self.api_service = ApiService()
        self.config = settings.ITEXTMO_CONFIG
    
    ## Generate OTP
    # @transaction.atomic
    def generate_otp(self, user_details):
        """Generate OTP"""
        
        mobile_no = user_details.get("mobile_no", "")
        otp_code = self.otp.generate(user_details=user_details)         
        
        ## Send OTP
        api_response = self.call_otp_api(mobile_no, otp_code)

        # return api_response
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
    

    # @transaction.atomic
    def call_otp_api(self, mobile_no, otp_code):
        """CALL OTP API"""

        url = self.config['ITEXTMO_BASE_URL']
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "Email": self.config['ITEXTMO_EMAIL'],
            "Password": self.config['ITEXTMO_PASSWORD'],
            "ApiCode": self.config['ITEXTMO_APICODE'],
            "Recipients": json.dumps([mobile_no]),
            "Message": f"Your OTP is {otp_code['code']}. It will expire in 5 minutes."
        }
        
        api_response = self.api_service.post_itext_mo(mobile_no=mobile_no, url = url, payload = payload, headers=headers)
        
        return api_response