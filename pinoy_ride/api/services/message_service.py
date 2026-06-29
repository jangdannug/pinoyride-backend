from django.db import transaction
from api.repositories import MessageRepository
from api.repositories import BookingRepository
from api.utils.custom_error import NotFoundError, ValidationError


class MessageService:

    def __init__(self):
        self.message = MessageRepository()
        self.booking = BookingRepository()

    def send_message(self, booking_id, sender_id, sender_type, message_text):
        """Send a message to a booking conversation"""
        if not booking_id:
            raise ValidationError("Booking ID is required")
        if not sender_id:
            raise ValidationError("Sender ID is required")
        if not sender_type:
            raise ValidationError("Sender type is required")
        if not message_text or message_text.strip() == "":
            raise ValidationError("Message text is required")

        # Validate sender_type
        if sender_type not in ['rider', 'customer']:
            raise ValidationError("Sender type must be 'rider' or 'customer'")

        # Check if booking exists
        booking = self.booking.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(f"Booking {booking_id} not found")

        # Create the message
        new_message = self.message.create_message(
            booking_id=booking_id,
            sender_id=sender_id,
            sender_type=sender_type,
            message_text=message_text.strip()
        )

        return new_message

    def get_conversation(self, booking_id, page_number=1, page_size=50, last_seen_id=None):
        """Get conversation history for a booking"""
        if not booking_id:
            raise ValidationError("Booking ID is required")

        # Check if booking exists
        booking = self.booking.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(f"Booking {booking_id} not found")

        # Get messages
        messages = self.message.get_messages_by_booking(
            booking_id=booking_id,
            page_number=page_number,
            page_size=page_size,
            last_seen_id=last_seen_id
        )

        return messages

    def mark_messages_read(self, booking_id, user_id, user_type):
        """Mark messages as read for a user"""
        if not booking_id:
            raise ValidationError("Booking ID is required")
        if not user_id:
            raise ValidationError("User ID is required")
        if not user_type:
            raise ValidationError("User type is required")

        # Check if booking exists
        booking = self.booking.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(f"Booking {booking_id} not found")

        # Mark messages as read
        updated_count = self.message.mark_messages_as_read(
            booking_id=booking_id,
            user_id=user_id,
            user_type=user_type
        )

        return {'marked_read_count': updated_count}

    def get_unread_count(self, booking_id, user_id, user_type):
        """Get count of unread messages for a user"""
        if not booking_id:
            raise ValidationError("Booking ID is required")
        if not user_id:
            raise ValidationError("User ID is required")

        # Check if booking exists
        booking = self.booking.get_by_id(booking_id)
        if not booking:
            raise NotFoundError(f"Booking {booking_id} not found")

        count = self.message.get_unread_count(
            booking_id=booking_id,
            user_id=user_id,
            user_type=user_type
        )

        return {'unread_count': count}
