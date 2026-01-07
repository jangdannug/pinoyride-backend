import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class TopPhEkycCallbackLogsModel(SoftDeleteModel):

    id = models.AutoField(primary_key=True)
    request_data = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
        ]
        db_table = "top_ph_ekyc_callback_logs"
        

    def __str__(self):
        return f"{self.id}"
