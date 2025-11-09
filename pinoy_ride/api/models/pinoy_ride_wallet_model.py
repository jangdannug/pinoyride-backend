import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .customer_model import Customer
from .rider_model import Rider

from storages.backends.s3boto3 import S3Boto3Storage


class PinoyRideWallet(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    ref_code = models.CharField(max_length=255, unique=True)
    user_id = models.IntegerField()
    user_type = models.CharField(max_length=255, null=True)
    type = models.CharField(max_length=255, null=True)
    avail_balance = models.FloatField(default=0)
    credit_amount = models.FloatField(default=0)
    debit_amount = models.FloatField(default=0)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ref_code']),
            models.Index(fields=['user_id']),
            models.Index(fields=['user_type']),
            models.Index(fields=['type']),
            models.Index(fields=['status'])
        ]
        db_table = "pinoy_ride_wallet"
        
    def save(self, *args, **kwargs):
        """Auto-generate form_number and six_digit_code before saving."""
        if not self.ref_code:
            self.ref_code = self.generate_form_number()
            
        super().save(*args, **kwargs)
        

    def generate_form_number(self):
        """Generate a unique, auto-incrementing form number while considering soft-deleted records."""

        with transaction.atomic(): 
            last_code_number = PinoyRideWallet.all_objects.aggregate(max_number=Max('ref_code'))['max_number']
            if last_code_number and str(last_code_number).isdigit():
                next_number = int(last_code_number) + 1
            else: 
                next_number = 1 
                
            code_num = str(next_number).zfill(6) 
            
            while PinoyRideWallet.all_objects.filter(ref_code=code_num).exists():
                next_number += 1
                code_num = str(next_number).zfill(6)

            
            return code_num

    def __str__(self):
        return f"{self.ref_code}"
