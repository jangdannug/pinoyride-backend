from django.db import transaction
from api.repositories import CustomerAddressRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class CustomerAddressService:
    
    def __init__(self):
        self.customer_address = CustomerAddressRepository()
    
    ## Save customer address
    @transaction.atomic
    def save_customer_address(self, customer_instance, customer_address):
        """Save customer address"""
        
        new_customer_address = self.customer_address.create(customer_instance = customer_instance, customer_address=customer_address)

        return new_customer_address
