import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class Promo(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    start_date = models.DateField(max_length=255,null=True)
    end_date = models.DateField(max_length=255,null=True)
    location = models.CharField(max_length=255)
    no_of_users = models.IntegerField(default=0)
    added_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['added_by']),
            models.Index(fields=['deleted_at']),
        ]
        db_table = "promo"
        

    def __str__(self):
        return f"{self.code} - {self.name}"
