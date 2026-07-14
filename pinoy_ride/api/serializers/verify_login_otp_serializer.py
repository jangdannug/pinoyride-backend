from rest_framework import serializers

class VerifyLoginOtpSerializer(serializers.Serializer):

    mobile_no = serializers.CharField(max_length=12)
    user_type = serializers.ChoiceField(choices=['customer', 'rider'])
    code = serializers.CharField(max_length=6)
