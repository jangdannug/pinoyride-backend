from rest_framework import serializers

class GenerateOtpSerializer(serializers.Serializer):
    
    mobile_no = serializers.CharField(max_length=12)
    user_type = serializers.CharField(max_length=255)