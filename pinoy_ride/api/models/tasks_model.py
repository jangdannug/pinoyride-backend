import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage

class Tasks(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    task_name = models.CharField(max_length=255, null=True)
    task_description = models.TextField(blank=True, null=True)
    added_by = models.IntegerField(default=0)
    updated_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['added_by']),
            models.Index(fields=['updated_by'])
        ]
        db_table = "tasks"
        

    def __str__(self):
        return f"{self.id}"
