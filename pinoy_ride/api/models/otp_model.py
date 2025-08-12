import random
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from datetime import timedelta


class Otp(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    mobile_no = models.CharField(max_length=255)
    code = models.CharField(max_length=6)
    user_type = models.CharField(max_length=255, null=True, blank=True)
    status = models.IntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['mobile_no']),
            models.Index(fields=['code']),
            models.Index(fields=['user_type'])
        ]
        db_table = "otp"
        
    def is_expired(self):
        return timezone.now() > self.expires_at
        

    @staticmethod
    def generate_otp():
        return str(random.randint(100000, 999999))

    def __str__(self):
        return f"{self.code} - {self.mobile_no}"
