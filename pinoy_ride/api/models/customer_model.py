import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max

from storages.backends.s3boto3 import S3Boto3Storage


class Customer(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=255, unique=True)
    customer_type = models.CharField(max_length=6, blank=True)
    fname = models.CharField(max_length=255)
    mname = models.CharField(max_length=255, null=True, blank=True)
    lname = models.CharField(max_length=255)
    mobile = models.CharField(max_length=255)
    email = models.CharField(max_length=255,null=True)
    is_verified = models.IntegerField(default=0)
    login_type = models.CharField(max_length=255, null=True)
    current_location = models.TextField(null=True)
    updated_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    customer_hash_code = models.CharField(max_length=255,null=True)
    session_id = models.CharField(max_length=255,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['login_type']),
            models.Index(fields=['current_location']),
            models.Index(fields=['status']),
            models.Index(fields=['updated_by']),
            models.Index(fields=['session_id']),
            models.Index(fields=['customer_hash_code']),
        ]
        db_table = "customer"
        
    def save(self, *args, **kwargs):
        """Auto-generate form_number and six_digit_code before saving."""
        if not self.code:
            self.code = self.generate_form_number()
            
        super().save(*args, **kwargs)
        

    def generate_form_number(self):
        """Generate a unique, auto-incrementing form number while considering soft-deleted records."""

        with transaction.atomic(): 
            last_code_number = Customer.all_objects.aggregate(max_number=Max('code'))['max_number']
            if last_code_number and str(last_code_number).isdigit():
                next_number = int(last_code_number) + 1
            else: 
                next_number = 1 
                
            code_num = str(next_number).zfill(6) 
            
            while Customer.all_objects.filter(code=code_num).exists():
                next_number += 1
                code_num = str(next_number).zfill(6)

            
            return code_num

    def __str__(self):
        return f"{self.code} - {self.fname} {self.lname}"
