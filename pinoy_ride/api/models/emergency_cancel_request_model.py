from django.conf import settings
from django.db import models

from .booking_model import Booking
from .rider_model import Rider
from .soft_delete_model import SoftDeleteModel


class EmergencyCancelRequest(SoftDeleteModel):
    """US-7.3: rider emergency cancel inside the penalty window, held for admin approval."""

    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED = "pending", "approved", "rejected"
    STATUS_CHOICES = [(STATUS_PENDING, "Pending"), (STATUS_APPROVED, "Approved"), (STATUS_REJECTED, "Rejected")]

    id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, related_name="emergency_cancel_requests", on_delete=models.CASCADE)
    rider = models.ForeignKey(Rider, related_name="emergency_cancel_requests", on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    # Worked out by rider_penalty at request time, so a later review doesn't change it.
    penalty_amount = models.FloatField(default=0)
    violation_count = models.IntegerField(default=0)
    scheduled_pickup_at = models.DateTimeField(null=True, blank=True)
    admin_reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="reviewed_emergency_cancels")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "emergency_cancel_request"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["booking_id", "rider_id"]),
        ]


def emergency_info(rider_id, booking_id, since=None):
    """Rider-side emergency fields for one booking (latest request by this rider)."""
    from django.utils import timezone
    req = None
    if rider_id and booking_id:
        qs = EmergencyCancelRequest.objects.filter(rider_id=rider_id, booking_id=booking_id)
        if since is not None:  # re-accepted booking: ignore requests from an earlier assignment
            qs = qs.filter(created_at__gte=since)
        req = qs.order_by("-created_at").first()
    if req is None:
        return {"is_emergency": False, "emergency_status": None, "emergency_penalty_amount": None,
                "emergency_admin_reason": None, "emergency_reviewed_at": None}
    return {"is_emergency": True, "emergency_status": req.status,
            "emergency_penalty_amount": round(float(req.penalty_amount or 0), 2),
            "emergency_admin_reason": req.admin_reason,
            "emergency_reviewed_at": timezone.localtime(req.reviewed_at).isoformat() if req.reviewed_at else None}
