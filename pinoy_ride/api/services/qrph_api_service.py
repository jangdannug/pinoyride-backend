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
from django.core.cache import cache


class QrphApiService:
    
    CACHE_KEY_TOKEN = 'qrph_auth_token'
    CACHE_KEY_EXPIRY = 'qrph_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.auth_base_url = 'https://pre-auth.theorangeplatform.com/'
        self.top_ph_base_url = 'https://pre-web.theorangeplatform.com/'
        self.login_code_api = 'connect/ext/clientidentity/v1/api/extclient/identity/login/code'
        self.request_to_pay_api = 'channel/epay/v1/api/client/top/epayment'
        self.username = 'topqrclient1'
        self.password = 'Password@2025'
        self.device_type = 'client_type_web_921b77e6-e4d0-4bb4-8225-339df8251c07'
        self.client_secret = 'I0nPnfRfbBFv1O0b9tc0NobCvimKyntUJb+DYxV8wps='      
        self.app_id = '921b77e6-e4d0-4bb4-8225-339df8251c07'
        self.api_key  = '339df8251c07'
    
    ## authenticate method
    def authenticate(self, force_refresh: bool = False):
        """Authenticate and get token"""

        # Check cache first
        if not force_refresh:
            cached_token = self._get_cached_token()
            if cached_token:
                app_logger(1, "Using cached QRPh token", {"token": cached_token, "expiry": cache.get(self.CACHE_KEY_EXPIRY)})
                return {"message" : "cached token", "result" : cached_token}
            
        auth_url = f"{self.auth_base_url}{self.login_code_api}"

        # Create credentials payload (order matters)
        credentials = {
            "password": self.password,
            "userName": self.username
        }

        exp_ms = self._get_expiration_ms()
        payload = self._create_payload(credentials, token="", exp_ms=exp_ms)

        headers = {
            "X-API-KEY": self.api_key
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
    
    ## request to pay method
    def request_to_pay(
        self,
        amount: float,
        total_amount: float,
        reference_id: str,
        client_title: str,
        client_logo: str,
        exp_in_mins: int = 30,
        discount: float = 0.0,
        tax: float = 0.0,
        trxn_fee: float = 0.0,  
        order_details: Optional[list] = None
    ) -> Dict[str, Any]:
        """Request to Pay"""
        request_to_pay_url = f"{self.top_ph_base_url}{self.request_to_pay_api}"

        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")

        # Build request data (order matters per API spec)
        data = {}   
        
        if order_details:
            data["orderDetails"] = order_details
        
        data["orderSummary"] = {
            "amount": amount,
            "totalAmount": total_amount,
            "discount": discount,
            "tax": tax,
            "trxnFee": trxn_fee,
            "referenceId": reference_id
        }
        
        data["clientInfo"] = {
            "title": client_title,
            "logo": client_logo
        }
        
        data["paymentMethod"] = 2  # QRPh
        data["expInMins"] = exp_in_mins
        
        payload = self._create_payload(data, token=auth_token)
        
        headers = {
            "X-API-KEY": self.api_key,
            "x-idempotent-key": str(uuid.uuid4())
        }
        
        app_logger(1, "Request to Pay", {
            "url": request_to_pay_url,
            "reference_id": reference_id,
            "raw_data": data,
            "token": auth_token,
        })
        
        response = self.api_service.post_request(url=request_to_pay_url, payload=payload, headers=headers)

        ## Throw error if request to pay failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to pay failed: {response.get('message')}")

        return response
    
    def _create_payload(
        self,
        data_dict: Dict[str, Any],
        token: str = " ",
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
        code_str = f"{token}.{exp_ms}.{self.device_type}"
        encoded_code = self._encode_base64(code_str)
        
        # Create salt and hash
        salt = f"{token}.{exp_ms}.{self.client_secret}.{self.device_type}"
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