from django.db import transaction
from api.repositories import WalletRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class WalletService:
    
    def __init__(self):
        self.wallet = WalletRepository()
    
    ## Save wallet
    @transaction.atomic
    def save_wallet(self, wallet_details):
        """Save wallet"""
        
        wallet = self.wallet.create(wallet_details = wallet_details)

        return wallet
