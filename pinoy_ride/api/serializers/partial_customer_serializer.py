from rest_framework import serializers
from api.models import Customer
from .customer_address_serializer import CustomerAddressSerializer

class PartialCustomerSerializer(serializers.ModelSerializer):

    customer_address = serializers.SerializerMethodField()
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
            "current_location",
            "status",
            "customer_address"
        ]


    
    def get_customer_address(self, obj):
        # get the related table customer_address
        address = obj.customer_address.filter(type=1).first()
        if address:
            return CustomerAddressSerializer(address).data
        return {}