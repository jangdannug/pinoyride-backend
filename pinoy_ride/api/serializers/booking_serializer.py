from rest_framework import serializers
from api.models import Booking, Customer
from .partial_customer_serializer import PartialCustomerSerializer
from .booking_payment_serializer import BookingPaymentSerializer
from .partial_rider_serializer import PartialRiderSerializer
from .booking_ratings_serializer import BookingRatingsSerializer


class BookingSerializer(serializers.ModelSerializer):

    ref_code = serializers.CharField(read_only=True)
    booking_type = serializers.CharField(required=True)
    pickup_location = serializers.CharField(required=True)
    pickup_lat = serializers.CharField(required=True)
    pickup_long = serializers.CharField(required=True)
    dropoff_location = serializers.CharField(required=True)
    dropoff_lat = serializers.CharField(required=True)
    dropoff_long = serializers.CharField(required=True)
    distance_km = serializers.CharField(read_only=True)
    payment_type = serializers.CharField(read_only=True)
    customer = PartialCustomerSerializer(read_only=True)
    note_to_rider = serializers.CharField(read_only=True)
    rider_details = serializers.SerializerMethodField()
    payment_details = serializers.SerializerMethodField()
    booking_ratings = serializers.SerializerMethodField()
    pretty_status = serializers.SerializerMethodField()

    # Map customer_id → customer (for writes)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source="customer",
        write_only=True,
        required=False,
        allow_null=True
    ) 

    class Meta:
        model = Booking
        fields = [
            "id",
            "ref_code",
            "booking_type",
            "pickup_location",
            "pickup_lat",
            "pickup_long",
            "dropoff_location",
            "dropoff_lat",
            "dropoff_long",
            "distance_km",
            "payment_type",
            "status", # 0 = Pending, 1 = Accepted, 2 = Trip Started, 3=Completed, 4=Cancelled, 9 = Deleted
            "pretty_status",
            "note_to_rider",
            "date_created",
            "time_created",
            "customer_id",
            "customer",
            "payment_details",
            "rider_details",
            "booking_ratings",
        ]

    def get_payment_details(self, obj):
        # get the related table booking_payment
        booking_payment = obj.booking_payment.first()
        if booking_payment:
            return BookingPaymentSerializer(booking_payment).data
        return {}

    def get_booking_ratings(self, obj):
        # get the related table booking_ratings
        booking_ratings = obj.booking_ratings.first()
        if booking_ratings:
            return BookingRatingsSerializer(booking_ratings).data
        return {}
    
    def get_rider_details(self, obj):
        # get the related table rider
        if obj.rider:
            return PartialRiderSerializer(obj.rider).data
        return {}

    def get_pretty_status(self, obj):
        status = 'Pending'
        if obj.status == 1:
            status = 'Accepted'
        elif obj.status == 2:
            status = "Trip Started"
        elif obj.status == 3:
            status = "Completed"
        elif obj.status == 4:
            status = "Cancelled"

        return status
    

    def validate(self, attrs):
        customer = attrs.get("customer")
        pickup_location = attrs.get("pickup_location")
        pickup_lat = attrs.get("pickup_lat")
        pickup_long = attrs.get("pickup_long")
        dropoff_location = attrs.get("dropoff_location")
        dropoff_lat = attrs.get("dropoff_lat")
        dropoff_long = attrs.get("dropoff_long")

        # Check if a booking with the same details already exists
        if Booking.objects.filter(
            customer=customer,
            pickup_location=pickup_location,
            pickup_lat=pickup_lat,
            pickup_long=pickup_long,
            dropoff_location=dropoff_location,
            dropoff_lat=dropoff_lat,
            dropoff_long=dropoff_long,
            status=0,
        ).exists():
            raise serializers.ValidationError(
                "A booking with the same details already exists."
            )

        return attrs