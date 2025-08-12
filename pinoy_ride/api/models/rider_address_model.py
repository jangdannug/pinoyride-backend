import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .rider_model import Rider
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class RiderAddress(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    rider = models.ForeignKey(Rider, related_name='rider_address', on_delete=models.CASCADE, default=None, null=True, blank=True)
    type = models.CharField(max_length=255, null=True)
    address = models.CharField(max_length=255, null=True)
    barangay = models.CharField(max_length=255, null=True)
    municipality_city = models.CharField(max_length=255, null=True)
    province = models.CharField(max_length=255, null=True)
    zip_code = models.CharField(max_length=255, null=True)
    latitude = models.TextField(null=True)
    longitude = models.TextField(null=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['rider_id']),
            models.Index(fields=['type']),
            models.Index(fields=['latitude']),
            models.Index(fields=['longitude']),
            models.Index(fields=['status']),
            models.Index(fields=['deleted_at'])
        ]
        db_table = "rider_address"

    def __str__(self):
        return f"{self.id} - {self.rider}"
