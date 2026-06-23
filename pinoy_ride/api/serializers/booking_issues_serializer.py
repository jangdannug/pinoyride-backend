from rest_framework import serializers
from api.models.booking_issues_model import BookingIssues


class BookingIssuesSerializer(serializers.ModelSerializer):
    """Serializer for BookingIssues model"""

    booking_id = serializers.IntegerField(source='booking.id', read_only=True)
    booking_code = serializers.CharField(source='booking.booking_code', read_only=True)

    class Meta:
        model = BookingIssues
        fields = [
            'id',
            'booking_id',
            'booking_code',
            'issue_txt',
            'status',
            'user_type',
            'reported_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
