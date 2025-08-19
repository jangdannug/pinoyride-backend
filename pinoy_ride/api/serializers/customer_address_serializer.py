from rest_framework import serializers
from api.models import CustomerAddress

class CustomerAddressSerializer(serializers.ModelSerializer):
    
    pretty_type = serializers.SerializerMethodField()

    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "customer_id",
            "type",
            "pretty_type",
            "address",
            "barangay",
            "municipality_city",
            "province",
            "zip_code",
            "latitude",
            "longitude"
        ]


    def get_pretty_type(self, obj):
        pretty_type = 'Others'
        if obj.type == "1":
            pretty_type = 'Home'
        elif obj.type == "2":
            pretty_type = "Work"
        elif obj.type == "3":
            pretty_type = "School"
        elif obj.type == "4":
            pretty_type = "Address"

        return pretty_type