import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .booking_model import Booking
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class BookingPayment(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, related_name='booking_payment', on_delete=models.CASCADE, default=None, null=True, blank=True)
    type = models.CharField(max_length=255, null=True)
    minimum_fare = models.FloatField(default=0, blank=True)
    pesos_per_km = models.FloatField(default=0, blank=True)
    booking_fee = models.FloatField(default=0, blank=True)
    base_amount = models.FloatField(default=0, blank=True, null=True)
    distance_km_round = models.FloatField(default=0, blank=True, null=True)
    tip = models.FloatField(default=0, blank=True)
    promo_discount = models.FloatField(default=0, blank=True)
    total_amount_wo_promo = models.FloatField(default=0, blank=True)
    total_amount = models.FloatField(default=0, blank=True)
    commission = models.FloatField(default=0, blank=True, null=True)
    rider_net_amount = models.FloatField(default=0, blank=True, null=True)
    all_payment_details = models.JSONField(default=dict, null=True, blank=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['booking_id'])
        ]
        db_table = "booking_payment"

    def __str__(self):
        return f"{self.id}"
