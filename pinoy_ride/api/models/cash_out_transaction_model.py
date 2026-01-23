import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class CashOutTransaction(SoftDeleteModel):

    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=250, null=True, db_index=True)
    user_type = models.CharField(max_length=50, null=True, db_index=True)
    trxn_reference_id = models.CharField(max_length=150, unique=True, db_index=True)
    acct_name = models.CharField(max_length=250, null=True)
    acct_no = models.CharField(max_length=250, null=True)
    bank_code = models.CharField(max_length=250, null=True)
    trx_date = models.CharField(max_length=250, null=True)
    invoice_no = models.CharField(max_length=250, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.CharField(max_length=250, null=True)
    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    callback_data = models.JSONField(blank=True, null=True)
    status = models.IntegerField(default=0)

    expires_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user_id']),
            models.Index(fields=['user_type']),
            models.Index(fields=['message']),
            models.Index(fields=['trxn_reference_id']),
            models.Index(fields=['bank_code']),
        ]
        db_table = "cash_out_transactions"
        

    def __str__(self):
        return f"{self.id} - {self.trxn_reference_id}"
