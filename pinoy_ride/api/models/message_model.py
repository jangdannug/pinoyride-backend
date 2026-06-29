from django.db import models
from .soft_delete_model import SoftDeleteModel
from .booking_model import Booking


class Message(SoftDeleteModel):
    """Model for chat messages between rider and customer"""
    id = models.AutoField(primary_key=True)
    booking = models.ForeignKey(Booking, related_name='messages', on_delete=models.CASCADE, null=True, blank=True)
    sender = models.IntegerField(help_text="User ID of the sender (rider or customer)")
    sender_type = models.CharField(max_length=20, help_text="Type of sender: 'rider' or 'customer'")
    message_text = models.TextField()
    is_read = models.IntegerField(default=0, help_text="0 = unread, 1 = read")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "messages"
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['sender']),
            models.Index(fields=['sender_type']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
            models.Index(fields=['booking_id', 'created_at']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.id} - Booking {self.booking_id}"
