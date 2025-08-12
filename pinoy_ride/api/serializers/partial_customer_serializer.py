from rest_framework import serializers
from api.models import Customer

class PartialCustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer
        fields = [
            "id",
            "code",
            "fname",
            "mname",
            "lname",
            "mobile",
            "email",
            "status",
        ]