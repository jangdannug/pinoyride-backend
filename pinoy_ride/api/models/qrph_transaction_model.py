import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class QrPhTransaction(SoftDeleteModel):
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('used', 'Used'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
        ('confirmation', 'Confirmation'),
    ]

    id = models.AutoField(primary_key=True)
    reference_id = models.CharField(max_length=50, unique=True, db_index=True)
    partner_reference_id = models.CharField(max_length=50, db_index=True)
    invoice_id = models.CharField(max_length=50, blank=True, null=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    trxn_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    client_title = models.CharField(max_length=255)
    order_details = models.JSONField(blank=True, null=True)

    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    callback_data = models.JSONField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    payment_url = models.TextField(blank=True)
    
    record_status = models.IntegerField(default=0)

    expires_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['record_status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['partner_reference_id']),
        ]
        db_table = "qrph_transactions"
        

    def __str__(self):
        return f"{self.id} - {self.reference_id}"
