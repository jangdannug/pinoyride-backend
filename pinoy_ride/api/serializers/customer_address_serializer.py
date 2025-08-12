from rest_framework import serializers
from api.models import CustomerAddress

class CustomerAddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "customer_id",
            "type",
            "address",
            "barangay",
            "municipality_city",
            "province",
            "zip_code",
            "latitude",
            "longitude"
        ]
