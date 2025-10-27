import base64
import hashlib
from typing import Dict, Any
from django.utils import timezone
from datetime import timedelta
from api.utils.app_logger import app_logger


class TopPhEkycSecurityUtil:
    """Handles all security operations for QRPh API"""
    
    @staticmethod
    def verify_callback_hash(salt: str, callback_data: str, callback_hash: str) -> bool:
        """
        Verify the hash of callback data
        """
        
        # Generate hash
        combined = callback_data + salt
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        computed_hash = base64.b64encode(hash_obj.digest()).decode('utf-8')
        
        is_valid = computed_hash == callback_hash
        
        app_logger(1, "Callback hash verification", {
            "is_valid": is_valid,
            "received_hash": callback_hash,
            "computed_hash": computed_hash
        })
        
        return is_valid