from rest_framework import serializers

class VerifyOtpSerializer(serializers.Serializer):
    
    mobile_no = serializers.CharField(max_length=12)
    user_type = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=6)