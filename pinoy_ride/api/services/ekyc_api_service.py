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

class EkycApiService:
    
    CACHE_KEY_TOKEN = 'qrph_auth_token'
    CACHE_KEY_EXPIRY = 'qrph_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.config = settings.TOP_PH_CONFIG
    
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
            "user_id": user_id
        })
        
        response = self.api_service.post_request(url=generate_url, payload=payload, headers=headers)

        ## Throw error if request to generate eKYC url failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Request to generate eKYC url failed: {response.get('message')}")

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