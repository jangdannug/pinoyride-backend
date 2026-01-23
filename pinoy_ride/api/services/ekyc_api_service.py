from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.base import (
    ApiService
)
import requests
from api.utils.app_logger import app_logger
import json
from django.utils import timezone
from datetime import timedelta
import base64
import hashlib
from api.utils.app_logger import app_logger
from typing import Dict, Any, Optional
import uuid
from django.conf import settings
from django.core.cache import cache
from api.utils.top_ph_ekyc_security import TopPhEkycSecurityUtil
from api.models.top_ph_ekyc_model import TopPhEkyc
from api.models.top_ph_ekyc_details_model import TopPhEkycDetails
from api.utils.customer_utils import CustomUtils
from api.repositories import RiderRepository, CustomerRepository

class EkycApiService:
    
    CACHE_KEY_TOKEN = 'ekyc_auth_token'
    CACHE_KEY_EXPIRY = 'ekyc_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.config = settings.TOP_PH_EKYC_CONFIG
        self.security = TopPhEkycSecurityUtil()
        self.rider = RiderRepository()
        self.customer = CustomerRepository()
    
    ## authenticate method
    def authenticate(self, force_refresh: bool = False):
        """Authenticate and get token"""

        # Check cache first
        if not force_refresh:
            cached_token = self._get_cached_token()
            if cached_token:
                app_logger(1, "Using cached EKYC token", {"token": cached_token, "expiry": cache.get(self.CACHE_KEY_EXPIRY)})
                return {"message" : "cached token", "result" : cached_token}
            
        auth_url = f"{self.config['AUTH_BASE_URL']}{self.config['LOGIN_CODE_API']}"

        # Create credentials payload (order matters)
        credentials = {
            "password": self.config['PASSWORD'],
            "userName": self.config['USERNAME']
        }

        exp_ms = self._get_expiration_ms()
        payload = self._create_payload(credentials, token="", exp_ms=exp_ms)

        headers = {
            "X-API-KEY": self.config['API_KEY'],
        }
        
        response = self.api_service.post_request(url=auth_url, payload=payload, headers=headers)

        ## Throw error if authentication failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Authentication failed: {response.get('message')}")
        
        ## save token and expiry in cache
        token = response.get('result')
        now = timezone.localtime(timezone.now())
        expiry = now + timedelta(minutes=1)  # Token valid for 45 mins
        self._cache_token(token, expiry)
        app_logger(1, "EKYC Authentication Successful", {"token": token, "expiry" : expiry})
        
        return response
    

    ## generate ekyc url method
    @transaction.atomic
    def generate_ekyc_url(
        self,
        user_id: str,
        user_type: str,
        success_url: Optional[str] = None,
        failed_url: Optional[str] = None,
        expired_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate eKYC URL"""

        generate_url = f"{self.config['EKYC_BASE_URL']}{self.config['GENERATE_EKYC_URL']}"
        
        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")
        user_type_code = "C" if user_type == "customer" else "R"

        if not auth_token:
            raise ValidationError("Failed to get authentication token")
        
        request_user_id = f"{user_id}-{user_type_code}{int(timezone.now().timestamp())}"

        # Build request data (order matters per API spec)
        data = {
            "userId": request_user_id
        }
        
        # Add client pages if provided
        if success_url or failed_url or expired_url:
            client_pages = {}
            if failed_url:
                client_pages["failed"] = failed_url
            if expired_url:
                client_pages["expired"] = expired_url
            if success_url:
                client_pages["success"] = success_url
            data["clientPages"] = client_pages
        
        exp_ms = self._get_expiration_ms()
        payload = self._create_payload(data, token=auth_token, exp_ms=exp_ms)
        
        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "Content-Type": "application/json",
            "accept": "*/*"
        }
        
        app_logger(1, "Generating eKYC URL", {
            "url": generate_url,
            "user_id": user_id,
            "raw_data": data,
            "token": auth_token,
        })

        # Check Record
        if TopPhEkyc.objects.filter(user_id=user_id, user_type=user_type, status="success").exists():
            raise ValidationError("Record already exists!")
    
        response = self.api_service.post_request(url=generate_url, payload=payload, headers=headers)

        ## Throw error if request to generate eKYC url failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to generate eKYC url failed: {response.get('message')}")

        #Save to database
        try:
            TopPhEkyc.objects.create(
                request_user_id=response.get('result', {}).get('userId'),
                user_id=user_id,
                user_type=user_type,
                zkyc_id=response.get('result', {}).get('zkycId'),
                top_ph_user_id=response.get('result', {}).get('userId'),
                ekyc_url=response.get('result', {}).get('zkycUrl'),
                trx_date=response.get('result', {}).get('trxDate'),
                status="pending"
            )
        except Exception as e:
            ## Ignore error message if duplicate error throws
            return response
        
        # Return API response
        return response

    
    ## Process callback method
    @transaction.atomic
    def process_callback(
        self,
        encoded_data: str,
        callback_hash: str
    ) -> Dict[str, Any]:
        """
        Process callback from TOP.ph eKYC
        """

        # Decode the data
        try:
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            callback_data = json.loads(decoded_data)
        except Exception as e:
            raise ValidationError(f"Invalid callback data format: {str(e)}")
        
        # Verify hash
        salt = self.config['CLIENT_SECRET']
        # if not self.security.verify_callback_hash(salt, decoded_data, callback_hash):
        #     raise ValidationError("Invalid callback hash - data may be tampered")
        
        status = callback_data.get('status', '').lower()
        zkycId = callback_data.get('zkycId', '')
        requestUserId = callback_data.get('userId', '')

        if not requestUserId:
            raise ValidationError("userId not found")
        
        try:
            ## Update record
            ekycRecord = TopPhEkyc.objects.get(request_user_id=requestUserId)
            ekycRecord.top_ph_user_id = callback_data.get('userId', "")
            ekycRecord.status = status
            ekycRecord.trx_date = callback_data.get('trxDate', "")
            ekycRecord.remarks=callback_data.get('remark', '')
            ekycRecord.result_code=callback_data.get('resultCode', '')
            ekycRecord.zkyc_id=callback_data.get('zkycId', '')

            ekycRecord.callback_data = callback_data
            
            if status == 'success':
                user_type = ekycRecord.user_type
                mobile_no = ekycRecord.user_id

                ekycRecord.completed_at = timezone.localtime(timezone.now())
                ekycRecord.is_success_kyc=1

                # Save rider or customer mobile number
                if user_type == 'rider':
                    rider_customer_id = self.save_rider_info(mobile_no, requestUserId)
                elif user_type == 'customer':
                    rider_customer_id = self.save_customer_info(mobile_no, requestUserId)

                ekycRecord.rider_customer_id = rider_customer_id

            ekycRecord.save()
            
            app_logger(1, "Callback processed", {
                "request_user_id": requestUserId,
                "status": status
            })
            
        except TopPhEkyc.DoesNotExist:
            # raise NotFoundError("zkycId not found")
            return callback_data
            
       
        app_logger(1, "Callback processed successfully", callback_data)
        
        return callback_data

    ## get user details in top ph
    @transaction.atomic
    def get_topph_user_details(
        self,
        ref_id: str
    ) -> Dict[str, Any]:
        """Get user details in top ph"""

        get_user_details_url = f"{self.config['EKYC_BASE_URL']}{self.config['GET_EKYC_USER_DETAILS']}"
        
        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")
        
        if not auth_token:
            raise ValidationError("Failed to get authentication token")
        
        # Build request data (order matters per API spec)
        # ref_id = user_id or zkyc_id
        data = {
            "refId": ref_id
        }
        
        exp_ms = self._get_expiration_ms()
        payload = self._create_payload(data, token=auth_token, exp_ms=exp_ms)
        
        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "Content-Type": "application/json",
            "accept": "*/*"
        }
        
        app_logger(1, "Get Top Ph EKYC User Details", {
            "url": get_user_details_url,
            "refId": ref_id,
            "raw_data": data,
            "token": auth_token,
        })
        
        response = self.api_service.post_request(url=get_user_details_url, payload=payload, headers=headers)
        ## Throw error if request to get eKYC user details fail
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to get eKYC user details failed: {response.get('message')}")

        result = response.get('result', {})
        kycId = result.get('kycId', "")
        mobileNo = CustomUtils.convert_mobile_no(result.get('phoneNumber', ""))

        try:
            ## Update record
            ekycDetailsRecord = TopPhEkycDetails.objects.get(generate_request_user_id=ref_id)
            ekycDetailsRecord.first_name=result.get('firstName', "")
            ekycDetailsRecord.middle_name=result.get('middleName', "")
            ekycDetailsRecord.last_name=result.get('lastName', "")
            ekycDetailsRecord.email_address=result.get('emailAddress', "")
            ekycDetailsRecord.mobile_no=result.get('phoneNumber', "")
            ekycDetailsRecord.pretty_mobile_no=mobileNo
            ekycDetailsRecord.date_of_birth=result.get('dateOfBirth', "")
            ekycDetailsRecord.place_of_birth=result.get('placeOfBirth', "")
            ekycDetailsRecord.nationality=result.get('nationality', "")
            ekycDetailsRecord.gender=result.get('gender', "")
            ekycDetailsRecord.current_country=result.get('currentCountry', "")
            ekycDetailsRecord.current_address=result.get('currentAddress', "")
            ekycDetailsRecord.permanent_country=result.get('permanentCountry', "")
            ekycDetailsRecord.permanent_address=result.get('permanentAddress', "")
            ekycDetailsRecord.nature_of_work=result.get('natureOfWork', "")
            ekycDetailsRecord.source_of_fund=result.get('sourceOfFund', "")
            ekycDetailsRecord.id_type=result.get('idType', "")
            ekycDetailsRecord.id_number=result.get('idNumber', "")
            ekycDetailsRecord.id_front=result.get('idFront', "")
            ekycDetailsRecord.id_back=result.get('idBack', "")
            ekycDetailsRecord.selfie=result.get('selfie', "")
            
            ekycDetailsRecord.save()
            
            # Update user info
            # self.update_rider_info(request_user_id=ref_id, ekycDetails=ekycDetailsRecord)

        except TopPhEkycDetails.DoesNotExist:
            # Save to database
            ekycDetailsRecord = TopPhEkycDetails.objects.create(
                generate_request_user_id=ref_id,
                kyc_id=kycId,
                first_name=result.get('firstName', ""),
                middle_name=result.get('middleName', ""),
                last_name=result.get('lastName', ""),
                email_address=result.get('emailAddress', ""),
                mobile_no=result.get('phoneNumber', ""),
                pretty_mobile_no=mobileNo,
                date_of_birth=result.get('dateOfBirth', ""),
                place_of_birth=result.get('placeOfBirth', ""),
                nationality=result.get('nationality', ""),
                gender=result.get('gender', ""),
                current_country=result.get('currentCountry', ""),
                current_address=result.get('currentAddress', ""),
                permanent_country=result.get('permanentCountry', ""),
                permanent_address=result.get('permanentAddress', ""),
                nature_of_work=result.get('natureOfWork', ""),
                source_of_fund=result.get('sourceOfFund', ""),
                id_type=result.get('idType', ""),
                id_number=result.get('idNumber', ""),
                id_front=result.get('idFront', ""),
                id_back=result.get('idBack', ""),
                selfie=result.get('selfie', "")
            )

            # Update user info
            # self.update_rider_info(request_user_id=ref_id, ekycDetails=ekycDetailsRecord)

        return response

    @transaction.atomic
    def save_rider_info(self, mobile_no, requestUserId):

        personal_details = {
            "ekyc_request_user_id" : requestUserId,
            "mobile_no" : mobile_no,
            "application_status": 1,
            "status" : 1,
            "is_success_kyc" : 1
        }
        
        rider_id = 0
        check_rider_record = self.rider.check_rider_by_mobile(rider=personal_details)
        if check_rider_record is None:
            # Insert record
            rider = self.rider.create(rider=personal_details)
            rider_id = rider.id

        return rider_id
    
    @transaction.atomic
    def save_customer_info(self, mobile_no, requestUserId):

        personal_details = {
            "ekyc_request_user_id" : requestUserId,
            "mobile" : mobile_no,
            "mobile_no" : mobile_no,
            "login_type" : "mobile_number",
            "customer_type" : "1",
            "status" : 1,
            "is_success_kyc" : 1
        }

        customer_id = 0
        check_customer_record = self.customer.check_customer_by_mobile(customer=personal_details)
        if check_customer_record is None:
            # Insert record
            customer = self.customer.create(customer=personal_details)
            customer_id = customer.id

        return customer_id
    

    # @transaction.atomic
    # def update_rider_info(self, request_user_id, ekycDetails):

    #     personal_details = {
    #         "first_name" : ekycDetails.first_name or "",
    #         "middle_name" : ekycDetails.middle_name or "",
    #         "last_name" : ekycDetails.last_name or "",
    #     }
        
    #     rider_record = self.rider.check_rider_by_request_user_id(request_user_id=request_user_id)
    #     if rider_record:
    #         # Update record
    #         rider = self.rider.update_rider_details(rider_instance=rider_record, personal_details=personal_details)

    #     app_logger(1, "Called 1",{})
    #     return


    ## check user details in top ph
    @transaction.atomic
    def check_topph_user_details(
        self,
        ekyc_request_user_id: str
    ) -> Dict[str, Any]:
        """Check details in top ph"""

        try:
            ekycDetailsRecord = TopPhEkycDetails.objects.get(generate_request_user_id=ekyc_request_user_id)
            return ekycDetailsRecord
        
        except TopPhEkycDetails.DoesNotExist:
            return None

    def _create_payload(
        self,
        data_dict: Dict[str, Any],
        token: str = "",
        exp_ms: Optional[int] = None
    ) -> Dict[str, str]:
        """Create request payload with data, code, and hash"""
        if exp_ms is None:
            exp_ms = self._get_expiration_ms()
        
        # Create JSON string (order matters per API spec)
        data_json = json.dumps(data_dict, separators=(',', ':'))
        
        # Encode data
        encoded_data = self._encode_base64(data_json)
        
        # Create and encode code
        code_str = f"{token}.{exp_ms}.{self.config['DEVICE_TYPE']}"
        encoded_code = self._encode_base64(code_str)
        
        # Create salt and hash
        salt = f"{token}.{exp_ms}.{self.config['CLIENT_SECRET']}.{self.config['DEVICE_TYPE']}"
        hash_value = self._generate_hash(data_json, salt)
        
        return {
            "data": encoded_data,
            "code": encoded_code,
            "hash": hash_value
        }
    
    def _get_cached_token(self) -> Optional[str]:
        """Get token from cache if valid"""
        token = cache.get(self.CACHE_KEY_TOKEN)
        expiry = cache.get(self.CACHE_KEY_EXPIRY)
        now = timezone.localtime(timezone.now())
        
        if token and expiry:
            if now < expiry:
                return token
        
        return None
    
    def _cache_token(self, token: str, expiry: timezone.datetime):
        """Cache token with expiry"""
        cache.set(self.CACHE_KEY_TOKEN, token, timeout=3600)  # 1 hour
        cache.set(self.CACHE_KEY_EXPIRY, expiry, timeout=3600)

    def _get_expiration_ms(self, hours: int = 1) -> int:
        """Generate expiration timestamp in milliseconds"""
        now = timezone.localtime(timezone.now())
        exp_time = now + timedelta(hours=hours)
        return int(exp_time.timestamp() * 1000)
    
    def _encode_base64(self, data: str) -> str:
        """Base64 encode string"""
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    def _generate_hash(self, data: str, salt: str) -> str:
        """Generate SHA-256 hash"""
        combined = data + salt
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        return base64.b64encode(hash_obj.digest()).decode('utf-8')

    def check_status(self, request_user_id: str):
        try:
            return TopPhEkyc.objects.filter(request_user_id=request_user_id).order_by('-id').first()
        except TopPhEkyc.DoesNotExist:
            return None
            