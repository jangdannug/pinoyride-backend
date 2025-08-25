import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .booking_model import Booking
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class BookingRatings(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, related_name='booking_ratings', on_delete=models.CASCADE, default=None, null=True, blank=True)
    rate = models.CharField(max_length=255, null=True)
    compliment = models.TextField(null=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['rate']),
            models.Index(fields=['booking_id'])
        ]
        db_table = "booking_ratings"

    def __str__(self):
        return f"{self.id}"
