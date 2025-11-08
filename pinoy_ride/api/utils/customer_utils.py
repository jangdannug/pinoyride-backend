import base64
import hashlib
from typing import Dict, Any
from django.utils import timezone
from datetime import timedelta
from api.utils.app_logger import app_logger


class CustomUtils:
    """Custom Utils"""
    
    @staticmethod
    def convert_mobile_no(mobile_no: str) -> str:
        """Convert mobile no"""
        
        # Get the last 10 digits
        last_10 = mobile_no[-10:]

        converted_mobile_no = f"63{last_10}"
        
        return str(converted_mobile_no)