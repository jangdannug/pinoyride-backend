from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.message_model import Message
from api.models.booking_model import Booking
from django.db import transaction
from django.utils.timezone import now
import logging

logger = logging.getLogger('myapp')


class MessageRepository:

    @staticmethod
    @transaction.atomic
    def create_message(booking_id, sender_id, sender_type, message_text):
        """Create a new message"""
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            logger.error(f"Booking {booking_id} not found")
            return None

        message = Message.objects.create(
            booking=booking,
            sender=sender_id,
            sender_type=sender_type,
            message_text=message_text,
            is_read=0
        )

        return message

    @staticmethod
    def get_messages_by_booking(booking_id, page_number=1, page_size=50, last_seen_id=None):
        """Get messages for a booking with pagination"""
        messages = Message.objects.filter(booking_id=booking_id).order_by('created_at')

        # If last_seen_id is provided, get only newer messages
        if last_seen_id:
            messages = messages.filter(id__gt=last_seen_id)

        # Paginate
        paginator = Paginator(messages, page_size)
        page_obj = paginator.get_page(page_number)

        # Build response data
        messages_data = []
        for message in page_obj:
            messages_data.append({
                'id': message.id,
                'booking_id': message.booking_id,
                'sender': message.sender,
                'sender_type': message.sender_type,
                'message_text': message.message_text,
                'is_read': message.is_read,
                'created_at': message.created_at.isoformat() if message.created_at else None,
            })

        return {
            'data': messages_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'items_per_page': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'last_message_id': messages_data[-1]['id'] if messages_data else None
            }
        }

    @staticmethod
    @transaction.atomic
    def mark_messages_as_read(booking_id, user_id, user_type):
        """
        Mark messages as read for a user.
        Marks messages sent TO this user (from the other party) as read.
        A message is "to me" if: sender_type != user_type OR (sender_type == user_type AND sender_id != user_id)
        """
        # Mark as read: messages NOT sent by the current user (both id and type must not match)
        updated_count = Message.objects.filter(
            booking_id=booking_id,
            is_read=0
        ).exclude(
            sender=user_id,
            sender_type=user_type
        ).update(is_read=1, updated_at=now())

        return updated_count

    @staticmethod
    def get_unread_count(booking_id, user_id, user_type):
        """
        Get count of unread messages for a user.
        Unread messages are those sent TO the user (not by the user) that haven't been read.
        """
        # Count unread messages NOT sent by the current user (both id and type must not match)
        return Message.objects.filter(
            booking_id=booking_id,
            is_read=0
        ).exclude(
            sender=user_id,
            sender_type=user_type
        ).count()

    @staticmethod
    def get_message_by_id(message_id):
        """Get a message by ID"""
        try:
            return Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return None
