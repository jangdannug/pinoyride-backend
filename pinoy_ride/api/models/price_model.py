import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage

class Price(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    price = models.IntegerField(default=0)
    km = models.IntegerField(default=0)
    time_travel = models.IntegerField(default=0)
    exceed_time_travel_price = models.IntegerField(default=0)
    added_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['km']),
            models.Index(fields=['exceed_time_travel_price']),
            models.Index(fields=['time_travel']),
            models.Index(fields=['status']),
            models.Index(fields=['added_by']),
            models.Index(fields=['deleted_at']),
        ]
        db_table = "price"
        

    def __str__(self):
        return f"{self.km}"
