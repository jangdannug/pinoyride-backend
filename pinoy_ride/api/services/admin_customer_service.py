from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
class AdminCustomerService:
    
    def __init__(self):
        self.customer = CustomerRepository()

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

