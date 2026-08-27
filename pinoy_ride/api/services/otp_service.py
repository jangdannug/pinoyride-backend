from django.db import transaction
from api.repositories import OtpRepository, RiderRepository, CustomerRepository
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
        self.rider = RiderRepository()
        self.customer = CustomerRepository()
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


    ## Generate Login OTP
    # @transaction.atomic
    def generate_login_otp(self, user_details):
        """Generate OTP for login"""

        mobile_no = user_details.get("mobile_no", "")
        user_type = user_details.get("user_type", "")

        # Validate that mobile_no exists in the respective table
        if user_type == 'rider':
            # Check if mobile number is already logged in as customer
            # if self.customer.check_rider_logged_in_by_mobile(mobile_no):
                # raise ValidationError("This mobile number is currently logged in as a customer. Please log out from the customer account first.")

            # Check if rider exists
            rider = self.rider.get_rider_by_mobile_for_login(mobile_no)
            if rider is None:
                raise ValidationError("Rider with this mobile number does not exist")
            # Check if rider is already logged in
            # if rider.is_login == 1:
                # raise ValidationError("This account is currently logged in. Please log out before logging in again.")
        elif user_type == 'customer':
            # Check if mobile number is already logged in as rider
            # if self.rider.check_customer_logged_in_by_mobile(mobile_no):
                # raise ValidationError("This mobile number is currently logged in as a rider. Please log out from the rider account first.")

            # Check if customer exists
            customer = self.customer.get_customer_by_mobile_for_login(mobile_no)
            if customer is None:
                raise ValidationError("Customer with this mobile number does not exist")
            # Check if customer is already logged in
            # if customer.is_login == 1:
                # raise ValidationError("This account is currently logged in. Please log out before logging in again.")
        else:
            raise ValidationError("Invalid user_type.")

        # Generate OTP
        otp_code = self.otp.generate(user_details=user_details)

        ## Send OTP
        api_response = self.call_otp_api(mobile_no, otp_code)

        return otp_code


    ## Verify Login OTP
    @transaction.atomic
    def verify_login_otp(self, otp_data):
        """Verify OTP for login"""

        mobile_no = otp_data.get("mobile_no", "")
        user_type = otp_data.get("user_type", "")

        # Validate that mobile_no exists in the respective table
        if user_type == 'rider':
            # Check if mobile number is already logged in as customer
            # if self.customer.check_rider_logged_in_by_mobile(mobile_no):
                # raise ValidationError("This mobile number is currently logged in as a customer. Please log out from the customer account first.")

            # Check if rider exists
            rider = self.rider.get_rider_by_mobile_for_login(mobile_no)
            if rider is None:
                raise ValidationError("Rider with this mobile number does not exist")
            # Check if rider is already logged in
            # if rider.is_login == 1:
                # raise ValidationError("This account is currently logged in. Please log out before logging in again.")
        elif user_type == 'customer':
            # Check if mobile number is already logged in as rider
            # if self.rider.check_customer_logged_in_by_mobile(mobile_no):
                # raise ValidationError("This mobile number is currently logged in as a rider. Please log out from the rider account first.")

            # Check if customer exists
            customer = self.customer.get_customer_by_mobile_for_login(mobile_no)
            if customer is None:
                raise ValidationError("Customer with this mobile number does not exist")
            # Check if customer is already logged in
            # if customer.is_login == 1:
                # raise ValidationError("This account is currently logged in. Please log out before logging in again.")
        else:
            raise ValidationError("Invalid user_type. Must be 'rider' or 'customer'")

        # Verify OTP
        otp_record = self.otp.check_if_exists(otp_data=otp_data)

        if otp_record is None:
            raise ValidationError("Invalid OTP")

        if otp_record.is_expired():
            raise ValidationError("OTP expired")
        

        app_version = otp_data.get("app_version", "")

        if user_type == 'rider':
            # Return FALSE if current version greater or equal than minimum
            if not self.compare_versions(app_version, '1.0.22'):
                # Update login status to 1 (logged in)
                self.rider.update_login_status(
                    rider_instance=rider,
                    status=1
                )

        elif user_type == 'customer':
            # Return FALSE if current version greater or equal than minimum
            if not self.compare_versions(app_version, '1.0.23'):
                # Update login status to 1 (logged in)
                self.customer.update_login_status(
                    customer_instance=customer,
                    status=1
                )

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
    

    def compare_versions(self, current_version, min_version):
        """Compare two version strings (e.g., '1.0.0' < '1.2.3' returns True)"""
        try:
            current_parts = list(map(int, current_version.split('.')))
            min_parts = list(map(int, min_version.split('.')))

            # Pad shorter version with zeros
            max_length = max(len(current_parts), len(min_parts))
            current_parts += [0] * (max_length - len(current_parts))
            min_parts += [0] * (max_length - len(min_parts))

            # Compare each part
            for c, m in zip(current_parts, min_parts):
                if c < m:
                    return True  # Current version is less than minimum
                elif c > m:
                    return False  # Current version is greater than minimum

            return False  # Versions are equal
        except (ValueError, AttributeError):
            # If version parsing fails, return False (allow request)
            return False