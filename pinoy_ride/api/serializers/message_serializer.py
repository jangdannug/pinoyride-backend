from rest_framework import serializers
from api.models.message_model import Message
import os


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    is_sent_by_me = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()
    image_msg = serializers.FileField(required=False, allow_null=True)
    image_msg_pretty = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'booking_id',
            'sender',
            'sender_type',
            'message_text',
            'image_msg',
            'image_msg_pretty',
            'is_read',
            'is_sent_by_me',
            'sender_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_is_sent_by_me(self, obj):
        """Determine if message was sent by the current user"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.sender == request.user.id
        # If no request/user, check context for current_user_id
        current_user_id = self.context.get('current_user_id')
        if current_user_id:
            return obj.sender == current_user_id
        return False

    def get_sender_name(self, obj):
        """Get sender name based on sender_type"""
        # This would need to query the appropriate user table
        # For now, return a placeholder
        if obj.sender_type == 'rider':
            return f"Rider {obj.sender}"
        return f"Customer {obj.sender}"

    def get_image_msg_pretty(self, obj):
        """Return full URL for the message image (mirrors RiderSerializer.get_ekyc_details selfie logic)"""
        image_url = ''
        if obj.image_msg and hasattr(obj.image_msg, 'name'):
            img_name = str(obj.image_msg.name)
            if img_name.startswith('http://') or img_name.startswith('https://'):
                image_url = img_name
            else:
                base_url = os.getenv('IMAGE_BASE_URL', 'http://127.0.0.1:7966/media')
                image_url = f"{base_url}/{img_name}"
        return image_url


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending a message (text and/or image)"""
    booking_id = serializers.IntegerField(required=True)
    sender_id = serializers.IntegerField(required=True)
    sender_type = serializers.CharField(required=False, default="customer")
    message_text = serializers.CharField(required=False, allow_blank=True, default="")
    image_msg = serializers.ImageField(required=False, allow_null=True)


class MarkReadSerializer(serializers.Serializer):
    """Serializer for marking messages as read"""
    booking_id = serializers.IntegerField(required=True)
    user_id = serializers.IntegerField(required=True)
    user_type = serializers.CharField(required=True)
