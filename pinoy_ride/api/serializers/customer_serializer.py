from rest_framework import serializers
from api.models import Customer
from .customer_address_serializer import CustomerAddressSerializer

class CustomerSerializer(serializers.ModelSerializer):

    code = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    email = serializers.CharField(required=True)
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
            "status",
            "customer_address"
        ]
    
    def validate_email(self, value):
        """Validate the email_address field to ensure it is unique (excluding soft-deleted records)"""
        queryset = Customer.objects.filter(email=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This email address already exists.")
        
        return value


    def validate_mobile(self, value):
        """Validate the mobile_no to ensure it is unique (excluding soft-deleted records)"""
        queryset = Customer.objects.filter(mobile=value, deleted_at__isnull=True)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)  # Exclude self when updating

        if queryset.exists():
            raise serializers.ValidationError("This mobile no already exists.")
        
        return value


    def get_customer_address(self, obj):
        # get the related table customer_address
        address = obj.customer_address.filter(type=1).first()
        if address:
            return CustomerAddressSerializer(address).data
        return {}