from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.rider_address_model import RiderAddress
from api.serializers import (
    PartialCustomerSerializer
)
from django.db import transaction

class RiderAddressRepository:
    
    @staticmethod
    @transaction.atomic
    def create(rider_instance, rider_address):
        new_rider_address = RiderAddress.objects.create(
            rider=rider_instance,
            type=rider_address.get("type", ""),
            address=rider_address.get("address", ""),
            barangay=rider_address.get("barangay", ""),
            municipality_city=rider_address.get("municipality_city", ""),
            province=rider_address.get("province", ""),
            zip_code=rider_address.get("zip_code", ""),
            latitude=rider_address.get("latitude", ""),
            longitude=rider_address.get("longitude", ""),
        )

        new_rider_address.save()
        
        return new_rider_address
