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

class EkycApiService:
    
    CACHE_KEY_TOKEN = 'ekyc_auth_token'
    CACHE_KEY_EXPIRY = 'ekyc_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.config = settings.TOP_PH_EKYC_CONFIG
        self.security = TopPhEkycSecurityUtil()
    
    ## authenticate method
    def authenticate(self, force_refresh: bool = False):
        """Authenticate and get token"""

        # Check cache first
        if not force_refresh:
            cached_token = self._get_cached_token()
            if cached_token:
                app_logger(1, "Using cached QRPh token", {"token": cached_token, "expiry": cache.get(self.CACHE_KEY_EXPIRY)})
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
        app_logger(1, "QRPh Authentication Successful", {"token": token, "expiry" : expiry})
        
        return response
    

    ## generate ekyc url method
    def generate_ekyc_url(
        self,
        user_id: str,
        success_url: Optional[str] = None,
        failed_url: Optional[str] = None,
        expired_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate eKYC URL"""

        generate_url = f"{self.config['EKYC_BASE_URL']}{self.config['GENERATE_EKYC_URL']}"
        
        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")
        
        if not auth_token:
            raise ValidationError("Failed to get authentication token")
        
        # Build request data (order matters per API spec)
        data = {
            "userId": user_id
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

        # response = self.api_service.post_request(url=generate_url, payload=payload, headers=headers)
        ## Simulated response
        response = {
            "version": "1.0",
            "statusCode": 200,
            "message": "POST Request successful.",
            "result": {
                "userId": "639411112111",
                "zkycId": "4841b809-4893-4ee9-b9f9-051022b502fb",
                "zkycUrl": "https://pre-zkyc.theorangeplatform.com/BUcjpNB4MkQlBkZl9TXNMkbDFlcGtNU0duQXAvWTF3WHNhZUdMMk5BakVUQUJiZ05OMD0=/hZKX1ElDKubG17VI8QkVgZWFJsVkdsdFpTSTZNVGMyTWpVM056VXpNekk0Tml3aWVtdDVZMGxrSWpvaU5EZzBNV0k0TURrdE5EZzVNeTAwWldVNUxXSTVaamt0TURVeE1ESXlZalV3TW1aaUlpd2lZMnhwWlc1MFNXUWlPaUpoTkRBMk0yVTVOUzFoWVRjMkxUUXlZVGt0T1RCbE5TMHlNakE0WW1Wa09EYzFNMklpTENKNmEzbGpVM1JsY0NJNk1Td2lkWE5sY2tsa0lqb2lOak01TkRFeE1URXlNVEV4SWl3aWRYSnNjeUk2ZXlKbVlXbHNaV1JWY213aU9pSm9kSFJ3Y3pvdkwzQnBibTk1Y21sa1pTNWpiMjB2Wm1GcGJHVmtMbWgwYld3aUxDSmxlSEJwY21Wa1ZYSnNJam9pYUhSMGNITTZMeTl3YVc1dmVYSnBaR1V1WTI5dEwyVjRjR2x5WlM1b2RHMXNJaXdpYzNWalkyVnpjMVZ5YkNJNkltaDBkSEJ6T2k4dmNHbHViM2x5YVdSbExtTnZiUzl6ZFdOalpYTnpMbWgwYld3aUxDSmpiMjVtYVhKdFlYUnBiMjVWY213aU9pSWlMQ0pqWVd4aVlXTnJWWEpzSWpvaWFIUjBjSE02THk5d2NtVXRZWEJ3TG5Sb1pXOXlZVzVuWlhCc1lYUm1iM0p0TG1OdmJTOXdZWGx0WVhSbEwzWXhMM0JoZVcxbGJuUXZjSEp2WTJWemMyOXlMMkYxWWk5bWRXNWtMM1J5WVc1elptVnlJbjBzSW5wdmJHOTZWWEpzSWpvaWFIUjBjSE02THk5elp5MXdjbTlrZFdOMGFXOXVMV05rYmk1NmIyeHZlaTVqYjIwdmNHRm5aUzk2YjJ4dmVpMXlaV0ZzYVdRdFptVXZhVzVrWlhndWFIUnRiQ0o5/GTlU6zRkBKd0dW1EJQXdRNREF0TURBd01DMHdNREF3TFRBd01EQXRNREF3TURBd01EQXdNREF3TG1FME1EWXpaVGsxTFdGaE56WXROREpoT1MwNU1HVTFMVEl5TURoaVpXUTROelV6WWk1b1ZEYzRUbXRHUmpkQmIxUmxha2wxUmxKQmQyZEJhV2wwV0ZwUVRXazFWV1JRUTNWQmVUVlJWVlJGUFM0eE56WXlOVGMyTXpNek16WTFMbVJsZG1salpWOTBlWEJsWDNwcmVXTmZZVFF3TmpObE9UVmhZVGMyTkRKaE9Ua3daVFV5TWpBNFltVmtPRGMxTTJJPQ==/uSFH9cNLtrbmf1xvmNm5BpRDNBYUx0eXQ5M2xLUFQvQ3czell2YUtOd0VlamxIbHF2TT0=",
                "trxDate": 1762604533
            }
        }

        ## Throw error if request to generate eKYC url failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to generate eKYC url failed: {response.get('message')}")

        #Save to database
        try:
            TopPhEkyc.objects.create(
                user_id=user_id,
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
        if not self.security.verify_callback_hash(salt, decoded_data, callback_hash):
            raise ValidationError("Invalid callback hash - data may be tampered")
        
        status = callback_data.get('status', '').lower()
        zkycId = callback_data.get('zkycId', '')
        if not zkycId:
            raise ValidationError("zkycId not found")
        
        try:
            ## Update record
            ekycRecord = TopPhEkyc.objects.get(zkyc_id=zkycId)
            ekycRecord.top_ph_user_id = callback_data.get('userId', "none")
            ekycRecord.status = status
            ekycRecord.trx_date = callback_data.get('trxDate', "none")
            ekycRecord.remarks=callback_data.get('remark', 'none')
            ekycRecord.result_code=callback_data.get('resultCode', 'none')

            ekycRecord.callback_data = callback_data
            
            if status == 'success':
                ekycRecord.completed_at = timezone.localtime(timezone.now())
            
            ekycRecord.save()
            
            app_logger(1, "Callback processed", {
                "zkyc_id": zkycId,
                "status": status
            })
            
        except TopPhEkyc.DoesNotExist:
            # Save to database
            TopPhEkyc.objects.create(
                user_id=callback_data.get('userId', "none"),
                top_ph_user_id=callback_data.get('userId', "none"),
                zkyc_id=callback_data.get('zkycId', "none"),
                status=callback_data.get('status').lower(),
                trx_date=callback_data.get('trxDate', 'none'),
                remarks=callback_data.get('remark', 'none'),
                result_code=callback_data.get('resultCode', 'none'),
                completed_at=timezone.localtime(timezone.now()),
                callback_data=callback_data
            )
            
       
        app_logger(1, "Callback processed successfully", callback_data)
        
        return callback_data

    ## get user details in top ph
    def get_topph_user_details(
        self,
        zkyc_id: str
    ) -> Dict[str, Any]:
        """Get user details in top ph"""

        get_user_details_url = f"{self.config['EKYC_BASE_URL']}{self.config['GET_EKYC_USER_DETAILS']}"
        
        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")
        
        if not auth_token:
            raise ValidationError("Failed to get authentication token")
        
        # Build request data (order matters per API spec)
        data = {
            "ref_id": zkyc_id
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
            "ref_id": zkyc_id,
            "raw_data": data,
            "token": auth_token,
        })
        
        response = self.api_service.post_request(url=get_user_details_url, payload=payload, headers=headers)

        # ## Throw error if request to get eKYC user details failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to get eKYC user details failed: {response.get('message')}")

        return response

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

    def check_status(self, zkyc_id: str):
        try:
            return TopPhEkyc.objects.filter(zkyc_id=zkyc_id).order_by('-id').first()
        except TopPhEkyc.DoesNotExist:
            return None
            