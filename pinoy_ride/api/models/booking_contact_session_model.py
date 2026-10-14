from django.db import models

from .booking_model import Booking
from .soft_delete_model import SoftDeleteModel


class BookingContactSession(SoftDeleteModel):
    """Per-booking masked proxy numbers for post-trip contact (24h window)."""

    id = models.AutoField(primary_key=True)
    booking = models.OneToOneField(
        Booking,
        related_name="contact_session",
        on_delete=models.CASCADE,
    )
    twilio_session_sid = models.CharField(max_length=64, null=True, blank=True)
    # What the customer sees / dials to reach the rider
    rider_proxy_number = models.CharField(max_length=32)
    # What the rider sees / dials to reach the customer
    customer_proxy_number = models.CharField(max_length=32)
    expires_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "booking_contact_session"
        indexes = [
            models.Index(fields=["booking_id"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"contact-session-{self.booking_id}"
