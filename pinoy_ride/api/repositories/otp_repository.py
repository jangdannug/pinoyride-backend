from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.otp_model import Otp
from api.serializers import (
    PartialRiderSerializer
)
from datetime import timedelta

from django.db import transaction

class OtpRepository:
    
    @staticmethod
    # @transaction.atomic
    def generate(user_details):
       
        otp_code = Otp.generate_otp()
        expires_at = timezone.now() + timedelta(minutes=5)  # OTP valid for 5 mins

        otp_obj, new_otp = Otp.objects.update_or_create(
            user_type=user_details.get("user_type", ""),
            mobile_no=user_details.get("mobile_no", ""),
            defaults={
                "code" : otp_code,
                "expires_at" : expires_at
            }
        )

        return {
            "user_type": otp_obj.user_type,
            "mobile_no": otp_obj.mobile_no,
            "code": otp_obj.code,
            "expires_at": otp_obj.expires_at
        }




    @staticmethod
    def check_if_exists(otp_data):
        try:
            otp_record = Otp.objects.get(
                mobile_no=otp_data.get("mobile_no", ""),
                user_type=otp_data.get("user_type", ""),
                code=otp_data.get("code", ""))
            return otp_record

        except Otp.DoesNotExist:
            return None
        
