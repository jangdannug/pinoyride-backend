from rest_framework import serializers
from api.models import Customer, TopPhEkycDetails
from .customer_address_serializer import CustomerAddressSerializer
from .top_ph_ekyc_details_serializer import TopPhEkycDetailsSerializer

class PartialCustomerSerializer(serializers.ModelSerializer):

    customer_address = serializers.SerializerMethodField()
    ekyc_details = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = [
            "id",
            "code",
            "is_login",
            "fname",
            "mname",
            "lname",
            "mobile",
            "email",
            "current_location",
            "status",
            "ekyc_details",
            "customer_address"
        ]


    
    def get_customer_address(self, obj):
        # get the related table customer_address
        address = obj.customer_address.filter(type=1).first()
        if address:
            return CustomerAddressSerializer(address).data
        return {}
    
    def get_ekyc_details(self, obj):
        try:
            record = TopPhEkycDetails.objects.get(generate_request_user_id=obj.ekyc_request_user_id)
            return TopPhEkycDetailsSerializer(record).data
        except TopPhEkycDetails.DoesNotExist:
            return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("omit_contact_phone"):
            data.pop("mobile", None)
            data.pop("email", None)
            ekyc = data.get("ekyc_details")
            if isinstance(ekyc, dict):
                for key in ("mobile_no", "pretty_mobile_no", "email_address"):
                    ekyc.pop(key, None)
        return data