import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .wallet_model import Wallet
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class WalletHistory(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    wallet = models.ForeignKey(Wallet, related_name='wallet_ref', on_delete=models.CASCADE, default=None, null=True, blank=True)
    type = models.CharField(max_length=255, null=True)
    credit_amount = models.FloatField(default=0)
    debit_amount = models.FloatField(default=0)
    time_created = models.CharField(max_length=255, null=True)
    date_created = models.CharField(max_length=255, null=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['wallet_id']),
            models.Index(fields=['type'])
        ]
        db_table = "wallet_history"

    def __str__(self):
        return f"{self.id} - {self.wallet}"
