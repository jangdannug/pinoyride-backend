import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage

def upload_to_driver_license_img(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return f"uploads/drivers_license_img/{instance.id}/{filename}"

class Rider(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=255, unique=True)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255,null=True, blank=True)
    last_name = models.CharField(max_length=255)
    mobile_no = models.CharField(max_length=255)
    email_address = models.CharField(max_length=255,null=True)
    drivers_license_no = models.CharField(max_length=255,null=True)
    drivers_license_no_expiration_date = models.DateField(max_length=255,null=True)
    drivers_license_img = models.FileField(upload_to=upload_to_driver_license_img, null=True, blank=True)
    application_status = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    updated_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['mobile_no']),
            models.Index(fields=['email_address']),
            models.Index(fields=['code']),
            models.Index(fields=['status']),
            models.Index(fields=['application_status']),
            models.Index(fields=['updated_by']),
            models.Index(fields=['deleted_at']),
        ]
        db_table = "riders"
        
    def save(self, *args, **kwargs):
        """Auto-generate form_number and six_digit_code before saving."""
        if not self.code:
            self.code = self.generate_form_number()
            
        super().save(*args, **kwargs)

    def generate_form_number(self):
        """Generate a unique, auto-incrementing form number while considering soft-deleted records."""

        with transaction.atomic(): 
            last_code_number = Rider.all_objects.aggregate(max_number=Max('code'))['max_number']
            if last_code_number and str(last_code_number).isdigit():
                next_number = int(last_code_number) + 1
            else: 
                next_number = 1 
                
            code_num = str(next_number).zfill(6) 
            
            while Rider.all_objects.filter(code=code_num).exists():
                next_number += 1
                code_num = str(next_number).zfill(6)

            
            return code_num

    def __str__(self):
        return f"{self.code} - {self.first_name} {self.last_name}"
