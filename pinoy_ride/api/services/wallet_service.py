from django.db import transaction
from api.repositories import WalletRepository, WalletHistoryRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class WalletService:
    
    def __init__(self):
        self.wallet = WalletRepository()
        self.wallet_history = WalletHistoryRepository()
    
    ## Save wallet
    @transaction.atomic
    def save_wallet(self, wallet_details):
        """Save wallet"""
        
        wallet = self.wallet.create(wallet_details = wallet_details)

        return wallet


    ## Get rider's wallet
    def get_rider_wallet(self,rider_id):
        """Get rider's wallet"""
        wallet = self.wallet.get_rider_wallet(rider_id=rider_id)
        
        if wallet is None:
            raise NotFoundError("Rider's wallet not found")
        return wallet
    
    ## Get customer's wallet
    def get_customer_wallet(self,customer_id):
        """Get customer's wallet"""
        wallet = self.wallet.get_customer_wallet(customer_id=customer_id)
        
        if wallet is None:
            raise NotFoundError("Customer's wallet not found")
        return wallet


    ## Create customer wallet
    def create_customer_wallet(self,customer_id):
        """Create customer wallet if not exist"""

        wallet = self.wallet.get_customer_wallet(customer_id=customer_id)
        if wallet is None:
            wallet_details = {
                "user_id" : customer_id,
                "user_type" : "customer",
                "type" : "user-wallet"
            }
            wallet = self.wallet.create(wallet_details=wallet_details)
            
        return wallet
    

    ## Create rider wallet
    def create_rider_wallet(self,rider_id):
        """Create rider wallet if not exist"""

        wallet = self.wallet.get_rider_wallet(rider_id=rider_id)
        if wallet is None:
            wallet_details = {
                "user_id" : rider_id,
                "user_type" : "rider",
                "type" : "user-wallet"
            }
            wallet = self.wallet.create(wallet_details=wallet_details)
            
        return wallet
    

    ## Top-up wallet
    def top_up(self,wallet_instance, top_up_details):
        """Get rider's wallet"""
        new_wallet_history = self.wallet_history.create(wallet_instance=wallet_instance, wallet_history=top_up_details)

        # Update wallet balance
        total_debit_credit = self.wallet_history.get_total_debit_credit(wallet_id=wallet_instance.id)

        wallet_details = {
            "credit_amount" : total_debit_credit['total_credit'],
            "debit_amount" : total_debit_credit['total_debit'],
            "avail_balance" : float(total_debit_credit['total_credit']) - float(total_debit_credit['total_debit']),
        }
        updated_wallet = self.wallet.update_balance(wallet_instance, wallet_details)
        
        return updated_wallet