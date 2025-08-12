from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.customer_address_model import CustomerAddress
from api.serializers import (
    PartialCustomerSerializer
)
from django.db import transaction

class CustomerAddressRepository:
    
    @staticmethod
    @transaction.atomic
    def create(customer_instance, customer_address):
        new_customer_address = CustomerAddress.objects.create(
            customer=customer_instance,
            type=customer_address.get("type", ""),
            address=customer_address.get("address", ""),
            barangay=customer_address.get("barangay", ""),
            municipality_city=customer_address.get("municipality_city", ""),
            province=customer_address.get("province", ""),
            zip_code=customer_address.get("zip_code", ""),
            latitude=customer_address.get("latitude", ""),
            longitude=customer_address.get("longitude", ""),
        )

        new_customer_address.save()
        
        return new_customer_address
