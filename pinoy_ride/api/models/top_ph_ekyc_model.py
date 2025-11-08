import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class TopPhEkyc(SoftDeleteModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('expired', 'Expired')
    ]

    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=150)
    zkyc_id = models.CharField(max_length=150, unique=True, db_index=True)
    user_type = models.CharField(max_length=150, null=True)
    top_ph_user_id = models.CharField(max_length=150, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    trx_date = models.CharField(max_length=150)
    remarks = models.CharField(max_length=250, null=True)
    result_code = models.CharField(max_length=50, null=True)
    callback_data = models.JSONField(blank=True, null=True)
    ekyc_url = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['result_code']),
            models.Index(fields=['user_id']),
            models.Index(fields=['zkyc_id']),
            models.Index(fields=['top_ph_user_id']),
            models.Index(fields=['user_type']),
        ]
        db_table = "top_ph_ekyc"
        

    def __str__(self):
        return f"{self.user_id} - {self.zkyc_id}"
