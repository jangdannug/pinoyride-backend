from rest_framework import serializers
from decimal import Decimal

class QRPhCallbackSerializer(serializers.Serializer):
    """Callback data validation"""
    referenceId = serializers.CharField(max_length=50)
    partner_ReferenceId = serializers.CharField(max_length=50)
    status = serializers.ChoiceField(choices=['Success', 'Failed', 'Expired', 'Confirmation'])
    invoiceId = serializers.CharField(max_length=50)
    trxDate = serializers.IntegerField()