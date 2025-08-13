from rest_framework import serializers
from api.models import RiderAddress

class RiderAddressSerializer(serializers.ModelSerializer):

    class Meta:
        model = RiderAddress
        fields = [
            "id",
            "rider_id",
            "type",
            "address",
            "barangay",
            "municipality_city",
            "province",
            "zip_code",
            "latitude",
            "longitude"
        ]
