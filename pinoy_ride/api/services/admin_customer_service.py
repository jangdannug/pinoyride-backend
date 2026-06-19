from django.db import transaction
from api.repositories import CustomerRepository, BookingRepository, WalletRepository
from api.utils.custom_error import NotFoundError, ValidationError
from api.utils.auth import get_authenticated_user
class AdminCustomerService:

    def __init__(self):
        self.customer = CustomerRepository()
        self.booking = BookingRepository()
        self.wallet = WalletRepository()

    ## Admin get list of customers
    def admin_customer_list(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all customers with pagination"""
        return self.customer.admin_customer_list(page_number, page_size, search_query, filters, sort_by)


    ## Get customer by id
    def get_customer_by_id(self,customer_id):
        """Fetch customer"""
        customer = self.customer.get_customer_by_id(customer_id=customer_id)
        
        if customer is None:
            raise NotFoundError("Customer "+ str(customer_id) + " not found")
        return customer


    ## Update customer status
    @transaction.atomic
    def update_customer_status(self, customer, customer_status, auth_user_id):
        """Update customer status"""

        update_customer = self.customer.update_customer_status(customer_instance=customer, customer_status=customer_status, auth_user_id=auth_user_id)
    
        return update_customer


     ## Admin get list of customer booking history
    def admin_list_customer_booking_history(self, customer_id, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all customer booking history with pagination"""
        return self.booking.admin_customer_booking_history(customer_id, page_number, page_size, search_query, filters, sort_by)


    ## Get customer wallet summary
    def get_customer_wallet_summary(self, customer_id):
        """Get customer wallet summary (current balance, total spent, total top-ups)"""
        return self.wallet.get_wallet_summary(user_id=customer_id, user_type='customer')


    ## Get customer wallet movements (all transactions)
    def get_customer_wallet_movements(self, customer_id, page_number=1, page_size=10):
        """Get customer wallet movements (all transactions) with pagination"""
        return self.wallet.get_recent_topups(user_id=customer_id, user_type='customer', page_number=page_number, page_size=page_size)