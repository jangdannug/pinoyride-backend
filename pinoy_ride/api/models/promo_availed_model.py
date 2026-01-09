import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4
from .promo_model import Promo
from .customer_model import Customer
from .booking_model import Booking

from storages.backends.s3boto3 import S3Boto3Storage

# status
# 0 = Inquire/Ongoing
# 1 = Completed
# 2 = Cancelled

class PromoAvailed(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    promo = models.ForeignKey(Promo, related_name='availed_promo', on_delete=models.CASCADE, default=None, null=True, blank=True)
    customer = models.ForeignKey(Customer, related_name='customer_promo', on_delete=models.CASCADE, default=None, null=True, blank=True)
    booking = models.ForeignKey(Booking, related_name='booking_promo', on_delete=models.CASCADE, default=None, null=True, blank=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['promo_id']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['booking_id']),
            models.Index(fields=['status']),
            models.Index(fields=['deleted_at']),
        ]
        db_table = "promo_availed"
        

    def __str__(self):
        return f"{self.id}"
