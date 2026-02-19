import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .booking_model import Booking
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class BookingIssues(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, related_name='booking_issues', on_delete=models.CASCADE, default=None, null=True, blank=True)
    issue_txt = models.TextField(null=True)
    status = models.IntegerField(default=0)
    user_type = models.CharField(max_length=150, default='customer', null=True)
    reported_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['status']),
            models.Index(fields=['user_type']),
            models.Index(fields=['reported_by'])
        ]
        db_table = "booking_issues"

    def __str__(self):
        return f"{self.id}"
