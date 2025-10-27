import base64
import hashlib
from typing import Dict, Any
from django.utils import timezone
from datetime import timedelta
from api.utils.app_logger import app_logger


class QRPhSecurityUtil:
    """Handles all security operations for QRPh API"""
    
    @staticmethod
    def generate_expiration_ms(hours: int = 1) -> int:
        """Generate expiration timestamp in milliseconds"""
        exp_time = timezone.now() + timedelta(hours=hours)
        return int(exp_time.timestamp() * 1000)
    
    @staticmethod
    def encode_base64(data: str) -> str:
        """Base64 encode string"""
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def decode_base64(data: str) -> str:
        """Base64 decode string"""
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def generate_hash(data: str, salt: str) -> str:
        """Generate SHA-256 hash with salt"""
        combined = f"{data}{salt}"
        hash_bytes = hashlib.sha256(combined.encode('utf-8')).digest()
        return base64.b64encode(hash_bytes).decode('utf-8')
    
    @staticmethod
    def verify_hash(data: str, salt: str, expected_hash: str) -> bool:
        """Verify hash matches expected value"""
        calculated = QRPhSecurityUtil.generate_hash(data, salt)
        app_logger(1, "Verifying hash", {
            "data": data,
            "salt": salt,
            "received_hash": expected_hash,
            "calculated_hash": calculated
        })
        return calculated == expected_hash
