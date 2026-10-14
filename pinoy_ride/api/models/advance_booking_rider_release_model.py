from django.db import models

from .booking_model import Booking
from .rider_model import Rider


class AdvanceBookingRiderRelease(models.Model):
    """Rider released an accepted advance booking back to the pool (rider history)."""

    booking = models.ForeignKey(
        Booking,
        related_name="rider_releases",
        on_delete=models.CASCADE,
    )
    rider = models.ForeignKey(
        Rider,
        related_name="advance_booking_releases",
        on_delete=models.CASCADE,
    )
    released_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "advance_booking_rider_release"
        indexes = [
            models.Index(fields=["rider_id", "released_at"]),
            models.Index(fields=["booking_id", "rider_id"]),
        ]
