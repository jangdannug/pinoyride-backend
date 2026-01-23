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
from api.models.cash_out_transaction_model import CashOutTransaction
from api.utils.qrph_security import QRPhSecurityUtil
class CashOutApiService:
    
    CACHE_KEY_TOKEN = 'cash_out_auth_token'
    CACHE_KEY_EXPIRY = 'cash_out_token_expiry'

    def __init__(self):
        self.api_service = ApiService()
        self.config = settings.CASH_OUT_CONFIG
        self.security = QRPhSecurityUtil()
        self.wallet_service = WalletService()
        
    
    ## authenticate method
    def authenticate(self, force_refresh: bool = False):
        """Authenticate and get token"""

        # Check cache first
        if not force_refresh:
            cached_token = self._get_cached_token()
            if cached_token:
                app_logger(1, "Using cached CashOut token", {"token": cached_token, "expiry": cache.get(self.CACHE_KEY_EXPIRY)})
                return {"message" : "cached token", "result" : cached_token}
            
        auth_url = f"{self.config['AUTH_BASE_URL']}{self.config['LOGIN_CODE_API']}"

        # Create credentials payload (order matters)
        credentials = {
            "password": self.config['PASSWORD'],
            "userName": self.config['USERNAME']
        }

        exp_ms = self._get_expiration_ms()
        payload = self._create_payload_v2(credentials, token="", exp_ms=exp_ms)

        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "X-APPID" : self.config['APP_ID']
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
    

    ## get_banks method
    @transaction.atomic
    def get_banks(
        self
    ) -> Dict[str, Any]:
        """Get Banks"""
        get_banks_url = f"{self.config['TOP_PH_BASE_URL']}{self.config['GET_BANKS_API']}"

        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")

        # Build request data (order matters per API spec)
        data = {}   
        
        data["appId"] = self.config['APP_ID']
        
        payload = self._create_payload_v2(data, token=auth_token)
        
        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "X-APPID" : self.config['APP_ID']
        }
        
        response = self.api_service.post_request(url=get_banks_url, payload=payload, headers=headers)

        ## Throw error if request to pay failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Get banks request failed: {response.get('message')}")
        
        result = response.get('result', {})

        remapped_result = []
        for bank in result.get("result", []):
            new_bank = {}
            
            new_bank["id"] = bank.get("bankID")
            new_bank["name"] = bank.get("bankName")
            new_bank["code"] = bank.get("bankCode")
            new_bank["num_code"] = bank.get("bankNumCode")
            new_bank["is_bank"] = bank.get("isBank")
            new_bank["is_qr"] = bank.get("isQr")
            new_bank["account_length"] = bank.get("bankALength")
            new_bank["is_maintenance"] = bank.get("isMaintenance")
            new_bank["type"] = bank.get("type")
            new_bank["logo_url"] = bank.get("logo")
            
            remapped_result.append(new_bank)

        return remapped_result


    ## cash-out method
    @transaction.atomic
    def cash_out(
        self,
        user_id: str,
        user_type: str,
        amount: float,
        destination_acct_name: str,
        destination_acct_no: str,
        destination_bank_code: str
    ) -> Dict[str, Any]:
        """Cash-Out"""
        cashout_url = f"{self.config['TOP_PH_BASE_URL']}{self.config['CASHOUT_API']}"

        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")

        # Generate unique trxn reference id
        user_type_code = "C" if user_type == "customer" else "R"
        tranRef_short = uuid.uuid4().hex[:8]  # 8-char hex
        ref_id = f"{user_id}{user_type_code}{int(timezone.now().timestamp())}-{tranRef_short}"


        # Build request data (order matters per API spec)
        data = {}   
        
        data["acctName"] = destination_acct_name
        data["acctNo"] = destination_acct_no
        data["bankCode"] = destination_bank_code
        data["id"] = ref_id
        data["txnAmt"] = str(amount)


        # Validate balance
        self.wallet_service.check_balance(user_id=user_id, user_type=user_type, amount=amount)
        
        payload = self._create_payload_v2(data, token=auth_token)
        
        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "X-APPID" : self.config['APP_ID']
        }
        
        app_logger(1, "Cash-Out Transaction", {
            "url": cashout_url,
            "reference_id": ref_id,
            "raw_data": data,
            "token": auth_token,
        })
        
        response = self.api_service.post_request(url=cashout_url, payload=payload, headers=headers)

        ## Throw error if cash-out failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Cash-out transaction failed: {response.get('message')}")
        
        result_data = response.get('result', {})
        result = result_data.get('result', {})

        status_msg =  'failed' 
        status_save = 0
        resp_message_status = result.get('message', '').lower()
        
        ## Validate staus
        if resp_message_status == 'accepted':
            #debit user wallets
            status_msg = 'success'
            status_save = 1
            ## call cashout internal method
            self.wallet_service.cash_out_users_wallet(user_type=user_type, user_id=user_id, amount=amount, reference_id=result.get('txnRefNo'))
        # else:
            # throw error
            # raise ValidationError(f"Cash-out transaction failed: {result.get('message')}")


        # Save to database
        transaction = CashOutTransaction.objects.create(
            user_id=user_id,
            user_type=user_type,
            trxn_reference_id=result.get('txnRefNo'),
            acct_name=destination_acct_name,
            acct_no=destination_acct_no,
            bank_code=destination_bank_code,
            trx_date=result.get('transactionDate'),
            invoice_no=result.get('invNo'),
            amount=result.get('txnAmt'),
            message=result.get('message'),
            request_payload=data,
            response_payload=response,
            status=status_save
        )

        return {
            "data": transaction,
            "response": result,
            "msg_status": status_msg
        }


    ## cashout check_status method
    @transaction.atomic
    def cashout_check_status(
        self,
        reference_id: str,
    ) -> Dict[str, Any]:
        """Cash Out Check Status"""
        inquire_url = f"{self.config['TOP_PH_BASE_URL']}{self.config['INQUIRE_API']}"

        # Get auth token
        auth_response = self.authenticate()
        auth_token = auth_response.get("result", "")

        # Build request data (order matters per API spec)
        data = {}   
        
        data["txnRefNo"] = reference_id
        
        payload = self._create_payload_v2(data, token=auth_token)
        
        headers = {
            "X-API-KEY": self.config['API_KEY'],
            "X-APPID" : self.config['APP_ID']
        }
        
        response = self.api_service.post_request(url=inquire_url, payload=payload, headers=headers)

        ## Throw error if request to pay failed
        if response.get('statusCode') not in [200, 201]:
            raise ValidationError(f"Get banks request failed: {response.get('message')}")
        
        result = response.get('result', {})

        return result
    
    def _create_payload_v2(
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
        salt = f"{self.config['APP_ID']}.{token}.{exp_ms}.{self.config['CLIENT_SECRET']}.{self.config['DEVICE_TYPE']}"
        hash_value = self._generate_hash(data_json, salt)
        
        app_logger(1, "Payload RAW ", {
            "data": data_json,
            "code": code_str,
            "salt": salt
        })

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
            return CashOutTransaction.objects.filter(reference_id=reference_id).order_by('-id').first()
        except CashOutTransaction.DoesNotExist:
            return None
            