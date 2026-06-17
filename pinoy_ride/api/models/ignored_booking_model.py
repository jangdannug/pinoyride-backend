import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .booking_model import Booking
from .rider_model import Rider

class IgnoredBooking(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    rider = models.ForeignKey(Rider, related_name='ignored_bookings', on_delete=models.CASCADE, default=None, null=True, blank=True)
    booking = models.ForeignKey(Booking, related_name='ignored_by', on_delete=models.CASCADE, default=None, null=True, blank=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['rider_id']),
            models.Index(fields=['booking_id']),
            models.Index(fields=['status'])
        ]
        db_table = "ignored_bookings"

    def __str__(self):
        return f"Ignored: {self.rider_id} - {self.booking_id}"
