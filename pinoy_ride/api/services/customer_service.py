from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class CustomerService:
    
    def __init__(self):
        self.customer = CustomerRepository()
    
    ## Save customer
    @transaction.atomic
    def save_customer(self, customer_details):
        """Save customer"""
        
        new_customer = self.customer.create(customer=customer_details)

        return new_customer



    ## Check customer by mobile_no
    def check_mobile_no(self, customer_details):
        """Check customer"""
        
        customer = self.customer.check_customer_by_mobile(customer=customer_details)

        if customer is None:
            raise NotFoundError("Customer not found")

        return customer

    ## Check customer by mobile_no
    def login_mobile_no(self, customer_details):
        """Check customer"""
        
        customer = self.customer.check_customer_by_mobile_kyc(customer=customer_details)

        if customer is None:
            raise NotFoundError("User not found")

        return customer
    
    ## Get customer by id
    def get_customer_by_id(self,customer_id):
        """Fetch customer"""
        customer = self.customer.get_customer_by_id(customer_id=customer_id)
        
        if customer is None:
            raise NotFoundError("Customer "+ str(customer_id) + " not found")
        return customer