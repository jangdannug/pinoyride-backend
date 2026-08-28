from django.db import transaction
from api.repositories import MessageRepository
from api.repositories import BookingRepository
from api.utils.custom_error import NotFoundError, ValidationError
from api.serializers import RiderSerializer, CustomerSerializer


class MessageService:

    def __init__(self):
        self.message = MessageRepository()
        self.booking = BookingRepository()

    def _get_conversation_details(self, booking):
        """Get rider and customer details for the conversation, based on each serializer's ekyc_details"""
        details = {
            'rider': {},
            'customer': {}
        }

        # Fields to display, sourced from ekyc_details (falls back to profile via serializer)
        display_fields = ['first_name', 'middle_name', 'last_name', 'mobile_no', 'selfie']

        # Rider details - pick fields from RiderSerializer's ekyc_details
        if booking.rider:
            rider_data = RiderSerializer(booking.rider).data
            rider_ekyc = rider_data.get('ekyc_details', {}) or {}
            details['rider'] = {field: rider_ekyc.get(field, '') for field in display_fields}

        # Customer details - pick fields from CustomerSerializer's ekyc_details
        if booking.customer:
            customer_data = CustomerSerializer(booking.customer).data
            customer_ekyc = customer_data.get('ekyc_details', {}) or {}
            details['customer'] = {field: customer_ekyc.get(field, '') for field in display_fields}

        return details

    def send_message(self, booking_id, sender_id, sender_type, message_text='', image_msg=None):
        """Send a message (text and/or image) to a booking conversation"""
        if not booking_id:
            raise ValidationError("Booking ID is required")
        if not sender_id:
            raise ValidationError("Sender ID is required")
        if not sender_type:
            raise ValidationError("Sender type is required")

        # At least one of message_text or image_msg must be provided
        if (message_text is None or message_text.strip() == '') and image_msg is None:
            raise ValidationError("Message text or image is required")

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
            message_text=message_text.strip() if message_text else '',
            image_msg=image_msg
        )

        return new_message

    def get_conversation(self, booking_id, page_number=1, page_size=50, last_seen_id=None, user_id=None, user_type=None):
        """Get conversation history for a booking with rider/customer details and unread count"""
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

        # Add rider and customer details
        messages['details'] = self._get_conversation_details(booking)

        # Add unread count based on user_id and user_type
        unread_count = 0
        if user_id and user_type:
            unread_count = self.message.get_unread_count(
                booking_id=booking_id,
                user_id=user_id,
                user_type=user_type
            )
        messages['unread_count'] = unread_count

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
