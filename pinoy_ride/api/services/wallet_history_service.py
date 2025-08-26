from django.db import transaction
from api.repositories import WalletHistoryRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class WalletHistoryService:
    
    def __init__(self):
        self.wallet_history = WalletHistoryRepository()
    
    ## Save wallet history
    @transaction.atomic
    def save_wallet_history(self, customer_instance, customer_address):
        """Save wallet history"""
        
        new_customer_address = self.wallet_history.create(customer_instance = customer_instance, customer_address=customer_address)

        return new_customer_address
