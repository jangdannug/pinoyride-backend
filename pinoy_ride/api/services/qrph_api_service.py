from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.base import (
    ApiService
)
from api.services import (
    WalletService
)
import requests
from api.utils.app_logger import app_logger
import json
from django.utils import timezone
from datetime import timedelta
import base64
import hashlib
from typing import Dict, Any, Optional
import uuid
from django.core.cache import cache
from django.conf import settings
from api.models.qrph_transaction_model import QrPhTransaction
from api.utils.qrph_security import QRPhSecurityUtil
class QrphApiService:
    
    CACHE_KEY_TOKEN = 'qrph_auth_token'
    CACHE_KEY_EXPIRY = 'qrph_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.config = settings.QRPH_CONFIG
        self.security = QRPhSecurityUtil()
    
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
    


    ## request to pay method
    @transaction.atomic
    def request_to_pay(
        self,
        user_id: str,
        user_type: str,
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
        request_to_pay_url = f"{self.config['TOP_PH_BASE_URL']}{self.config['REQUEST_TO_PAY_API']}"

        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")

        # Generate unique partner reference
        partner_ref =  str(uuid.uuid4())

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
            "X-API-KEY": self.config['API_KEY'],
            "x-idempotent-key": partner_ref
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
        
        result = response.get('result', {})

        # Save to database
        transaction = QrPhTransaction.objects.create(
            user_id=user_id,
            user_type=user_type,
            reference_id=result.get('referenceId'),
            partner_reference_id=partner_ref,
            invoice_id=result.get('invoiceId'),
            amount=amount,
            total_amount=total_amount,
            discount=discount,
            tax=tax,
            trxn_fee=trxn_fee,
            status='requested',
            payment_url=result.get('url'),
            client_title=client_title,
            order_details=order_details,
            expires_at=timezone.localtime(timezone.now()) + timedelta(minutes=exp_in_mins),
            request_payload=data,
            response_payload=response
        )

        return {
            "transaction": transaction,
            "response": result
        }



    # process callback method
    @transaction.atomic
    def process_callback(
        self,
        callback_data: Dict[str, Any],
        callback_hash: str
    ) -> QrPhTransaction:
        """Process and verify callback"""

        # Decode the data
        try:
            decoded_data = base64.b64decode(callback_data).decode('utf-8')
            callback_data = json.loads(decoded_data)
        except Exception as e:
            raise ValidationError(f"Invalid callback data format: {str(e)}")
        

        # Verify hash
        # data_json = json.dumps(callback_data, separators=(',', ':'))
        # is_valid = self.security.verify_hash(data_json, self.config['APP_ID'], callback_hash)
        # is_valid = self.security.verify_hash(decoded_data, self.config['APP_ID'], callback_hash)
        
        # if not is_valid:
        #     app_logger(2, "Invalid callback hash", callback_data)
        #     raise ValidationError("Invalid callback hash")
        
        reference_id = callback_data.get('referenceId')
        status = callback_data.get('status', '').lower()
        
        try:
            transaction = QrPhTransaction.objects.get(reference_id=reference_id)
            transaction.status = status
            transaction.callback_data = callback_data
            transaction.invoice_id = callback_data.get('invoiceId')
            transaction.topph_partner_reference_id=callback_data.get('partner_ReferenceId')
            transaction.trx_date=callback_data.get('trxDate')
            
            if status == 'success':
                transaction.completed_at = timezone.localtime(timezone.now())
                user_id = transaction.user_id
                user_type = transaction.user_type
                amount = transaction.total_amount

                # top-up users's wallet 
                self.top_up_users_wallet(user_type, user_id, amount, reference_id)
            
            transaction.save()
            
            app_logger(1, "Callback processed", {
                "reference_id": reference_id,
                "status": status
            })
            
            return transaction
            
        except QrPhTransaction.DoesNotExist:
            app_logger(3, "Callback for unknown transaction", callback_data)
            raise ValidationError(f"Transaction not found: {reference_id}")

    # Top up user's wallet
    @transaction.atomic
    def top_up_users_wallet(self, user_type, user_id, amount, reference_id):
        wallet_service = WalletService()
        return wallet_service.top_up_users_wallet(user_type = user_type, user_id = user_id, amount=amount, reference_id=reference_id)
    
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
    
    def check_status(self, reference_id: str):
        try:
            return QrPhTransaction.objects.filter(reference_id=reference_id).order_by('-id').first()
        except QrPhTransaction.DoesNotExist:
            return None
            