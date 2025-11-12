from django.db import transaction
from api.repositories import WalletRepository, WalletHistoryRepository, BookingPaymentRepository, PinoyRideWalletHistoryRepository, PinoyRideWalletRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
from api.utils.app_logger import app_logger
class WalletService:
    
    def __init__(self):
        self.wallet = WalletRepository()
        self.wallet_history = WalletHistoryRepository()
        self.booking_payment_repository = BookingPaymentRepository()
        self.pinoy_ride_wallet = PinoyRideWalletRepository()
        self.pinoy_ride_wallet_history = PinoyRideWalletHistoryRepository()
    
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
    @transaction.atomic
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
    @transaction.atomic
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
    
    ## Top-up customer's wallet
    @transaction.atomic
    def top_up_users_wallet(self, user_type, user_id, amount, reference_id):
        """Top up user's wallet"""

        top_up_details = {
            "type" : "credit",
            "credit_amount" : amount,
            "description" : f"Top-up|Ref-{reference_id}"
        }

        if user_type == 'customer':
            wallet_instance = self.wallet.get_customer_wallet(customer_id=user_id)

        else:
            wallet_instance = self.wallet.get_rider_wallet(rider_id=user_id)
        

        if wallet_instance:
            # insert to wallet history
            self.wallet_history.create(wallet_instance=wallet_instance, wallet_history=top_up_details)
            # Update wallet balance
            total_debit_credit = self.wallet_history.get_total_debit_credit(wallet_id=wallet_instance.id)

            wallet_details = {
                "credit_amount" : total_debit_credit['total_credit'],
                "debit_amount" : total_debit_credit['total_debit'],
                "avail_balance" : float(total_debit_credit['total_credit']) - float(total_debit_credit['total_debit']),
            }
            updated_wallet = self.wallet.update_balance(wallet_instance, wallet_details)
            
            return updated_wallet
            
    ## check balance
    def check_balance(self, user_id, user_type, amount):
        """Top up user's wallet"""
        avail_balance = 0
        if user_type == 'customer':
            wallet_instance = self.wallet.get_customer_wallet(customer_id=user_id)
        else:
            wallet_instance = self.wallet.get_rider_wallet(rider_id=user_id)
        
        total_debit_credit = self.wallet_history.get_total_debit_credit(wallet_id=wallet_instance.id)
        avail_balance = float(total_debit_credit['total_credit']) - float(total_debit_credit['total_debit'])

        if avail_balance < amount:
            raise ValidationError('Insufficient balance!')

        return          


    ## Update booking wallets
    @transaction.atomic
    def update_booking_wallets(self, booking_details):
        """Top up user's wallet"""

        booking_id = booking_details.id
        booking_payment = self.booking_payment_repository.get_by_id(booking_id=booking_id)

        if booking_payment:
            
            commission = booking_payment.commission
            rider_net_amount = booking_payment.rider_net_amount

            #-----#-----#-----#-----#-----#-----#-----#-----#-----
            # Customer
            customer_id = booking_details.customer_id
            
            # Check balance
            self.check_balance(user_id=customer_id, user_type='customer', amount=booking_payment.total_amount)
        
            customer_wallet_instance = self.wallet.get_customer_wallet(customer_id=customer_id)
            debit_details = {
                "booking_id" : booking_id,
                "type" : "debit",
                "debit_amount" : booking_payment.total_amount,
                "description" : f"Debit|Ref-{booking_details.ref_code}"
            }
            # insert to wallet history
            self.wallet_history.create(wallet_instance=customer_wallet_instance, wallet_history=debit_details)
            # Update wallet balance
            total_debit_credit = self.wallet_history.get_total_debit_credit(wallet_id=customer_wallet_instance.id)

            wallet_details = {
                "credit_amount" : total_debit_credit['total_credit'],
                "debit_amount" : total_debit_credit['total_debit'],
                "avail_balance" : float(total_debit_credit['total_credit']) - float(total_debit_credit['total_debit']),
            }
            self.wallet.update_balance(customer_wallet_instance, wallet_details)
            
          
            #-----#-----#-----#-----#-----#-----#-----#-----#-----#-----
            # Rider
            rider_id = booking_details.rider_id
            rider_wallet_instance = self.wallet.get_rider_wallet(rider_id=rider_id)
            
            credit_details = {
                "booking_id" : booking_id,
                "type" : "credit",
                "credit_amount" : rider_net_amount,
                "description" : f"Credit|Ref-{booking_details.ref_code}"
            }
            # insert to wallet history
            self.wallet_history.create(wallet_instance=rider_wallet_instance, wallet_history=credit_details)
            # Update wallet balance
            r_total_debit_credit = self.wallet_history.get_total_debit_credit(wallet_id=rider_wallet_instance.id)

            rider_wallet_details = {
                "credit_amount" : r_total_debit_credit['total_credit'],
                "debit_amount" : r_total_debit_credit['total_debit'],
                "avail_balance" : float(r_total_debit_credit['total_credit']) - float(r_total_debit_credit['total_debit']),
            }
            self.wallet.update_balance(rider_wallet_instance, rider_wallet_details)

           
            #-----#-----#-----#-----#-----#-----#-----#-----#-----#-----
            # Pinoy Ride Wallet
            
            pr_wallet_instance = self.pinoy_ride_wallet.get_wallet(user_id=1)
            
            pr_credit_details = {
                "booking_id" : booking_id,
                "type" : "credit",
                "credit_amount" : commission,
                "description" : f"Credit|Ref-{booking_details.ref_code}"
            }
            # insert to pinoy ride wallet history
            self.pinoy_ride_wallet_history.create(wallet_instance=pr_wallet_instance, wallet_history=pr_credit_details)
            # Update wallet balance
            pr_total_debit_credit = self.pinoy_ride_wallet_history.get_total_debit_credit(wallet_id=pr_wallet_instance.id)

            pr_wallet_details = {
                "credit_amount" : pr_total_debit_credit['total_credit'],
                "debit_amount" : pr_total_debit_credit['total_debit'],
                "avail_balance" : float(pr_total_debit_credit['total_credit']) - float(pr_total_debit_credit['total_debit']),
            }
            self.pinoy_ride_wallet.update_balance(wallet_instance=pr_wallet_instance, wallet_details=pr_wallet_details)

        return 
    
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