import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .customer_model import Customer
from .rider_model import Rider

from storages.backends.s3boto3 import S3Boto3Storage


class Booking(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    ref_code = models.CharField(max_length=255, unique=True)
    customer = models.ForeignKey(Customer, related_name='customer_booking', on_delete=models.CASCADE, default=None, null=True, blank=True)
    rider = models.ForeignKey(Rider, related_name='rider_booking', on_delete=models.CASCADE, default=None, null=True, blank=True)
    pickup_location = models.CharField(max_length=255, null=True)
    dropoff_location = models.CharField(max_length=255, null=True)
    pickup_lat = models.CharField(max_length=255, null=True)
    pickup_long = models.CharField(max_length=255, null=True)
    dropoff_lat = models.CharField(max_length=255, null=True)
    dropoff_long = models.CharField(max_length=255, null=True)
    distance_km = models.CharField(max_length=255, null=True)
    payment_type = models.CharField(max_length=255, null=True)
    note_to_rider = models.TextField(null=True)
    updated_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ref_code']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['rider_id']),
            models.Index(fields=['updated_by']),
            models.Index(fields=['status'])
        ]
        db_table = "booking"
        
    def save(self, *args, **kwargs):
        """Auto-generate form_number and six_digit_code before saving."""
        if not self.ref_code:
            self.ref_code = self.generate_form_number()
            
        super().save(*args, **kwargs)
        

    def generate_form_number(self):
        """Generate a unique, auto-incrementing form number while considering soft-deleted records."""

        with transaction.atomic(): 
            last_code_number = Booking.all_objects.aggregate(max_number=Max('ref_code'))['max_number']
            if last_code_number and str(last_code_number).isdigit():
                next_number = int(last_code_number) + 1
            else: 
                next_number = 1 
                
            code_num = str(next_number).zfill(6) 
            
            while Booking.all_objects.filter(ref_code=code_num).exists():
                next_number += 1
                code_num = str(next_number).zfill(6)

            
            return code_num

    def __str__(self):
        return f"{self.ref_code}"
