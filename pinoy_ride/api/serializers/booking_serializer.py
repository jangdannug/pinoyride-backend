from rest_framework import serializers
from api.models import Booking, Customer
from api.utils.vehicle_plate_utils import pretty_vehicle_type
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
    vehicle = serializers.SerializerMethodField()
    is_advance = serializers.BooleanField(read_only=True)
    scheduled_pickup_at = serializers.SerializerMethodField()
    rider_arrived_at = serializers.SerializerMethodField()
    arrived = serializers.SerializerMethodField()
    booking_label = serializers.SerializerMethodField()
    vehicle_type_label = serializers.SerializerMethodField()
    cancelled_by = serializers.CharField(read_only=True)
    penalty_amount = serializers.SerializerMethodField()
    returned_to_pool_at = serializers.SerializerMethodField()
    # When the booking last entered the pending pool (created_at; retry resets it)
    pooled_at = serializers.SerializerMethodField()
    # True once a rider holds the booking (status 1/2, or an accepted advance booking still at 5)
    rider_assigned = serializers.SerializerMethodField()

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
            "vehicle",
            "is_advance",
            "scheduled_pickup_at",
            "rider_arrived_at",
            "arrived",
            "booking_label",
            "vehicle_type_label",
            "cancelled_by",
            "penalty_amount",
            "returned_to_pool_at",
            "pooled_at",
            "rider_assigned",
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
            data = PartialRiderSerializer(obj.rider, context=self.context).data
            # Apps read vehicle_details[0]; put the vehicle used on this booking first
            # (snapshot vehicle, else the rider's current one) for instant and advance alike.
            vehicles = list(data.get("vehicle_details") or [])
            target = obj.rider_vehicle_id
            vehicles.sort(key=lambda v: (
                0 if (target and v.get("id") == target) else (1 if (not target and v.get("is_current")) else 2)
            ))
            data["vehicle_details"] = vehicles
            return data
        return {}

    @staticmethod
    def _rider_cancel_penalty_amount(rider_id, booking_id):
        if not rider_id:
            return 0.0
        from api.models.wallet_history_model import WalletHistory
        rows = WalletHistory.objects.filter(
            booking_id__in=(str(booking_id), booking_id),
            tran_type="cancel_penalty",
            type="debit",
            wallet__user_type="rider",
            wallet__user_id=rider_id,
        )
        return round(sum(float(r.debit_amount or 0) for r in rows), 2)

    def _rider_released_in_history(self, obj):
        rider_id = self.context.get("history_rider_id")
        if not rider_id or obj.rider_id == rider_id:
            return False
        from api.models.advance_booking_rider_release_model import AdvanceBookingRiderRelease
        if AdvanceBookingRiderRelease.objects.filter(
            booking_id=obj.id, rider_id=rider_id
        ).exists():
            return True
        return self._rider_cancel_penalty_amount(rider_id, obj.id) > 0

    def get_pretty_status(self, obj):
        if self._rider_released_in_history(obj):
            return "Cancelled"
        status = 'Pending'
        if obj.status == 1:
            status = 'Accepted'
        elif obj.status == 2:
            status = "Trip Started"
        elif obj.status == 3:
            status = "Completed"
        elif obj.status == 4:
            status = "Cancelled"
        elif obj.status == 5:
            if obj.is_advance and obj.returned_to_pool_at and not obj.rider_id:
                status = "Returned to pool"
            else:
                status = "Scheduled"

        return status

    @staticmethod
    def _local_iso(dt):
        from django.utils import timezone
        return timezone.localtime(dt).isoformat() if dt else None

    def get_scheduled_pickup_at(self, obj):
        return self._local_iso(obj.scheduled_pickup_at)

    def get_rider_arrived_at(self, obj):
        return self._local_iso(obj.rider_arrived_at)

    def get_rider_assigned(self, obj):
        return obj.rider_id is not None and obj.status in (1, 2, 5)

    def get_pooled_at(self, obj):
        return self._local_iso(obj.created_at)

    def get_arrived(self, obj):
        return obj.rider_arrived_at is not None

    def get_booking_label(self, obj):
        return "Advance Booking" if obj.is_advance else None

    def get_vehicle_type_label(self, obj):
        return pretty_vehicle_type(obj.booking_type) if obj.booking_type else None

    def get_returned_to_pool_at(self, obj):
        return self._local_iso(obj.returned_to_pool_at)

    def get_penalty_amount(self, obj):
        history_rider_id = self.context.get("history_rider_id")
        if history_rider_id:
            # Rider history/detail: only debits on this rider's wallet (not passenger penalties).
            return self._rider_cancel_penalty_amount(history_rider_id, obj.id)
        if obj.status != 4 or not obj.cancelled_by:
            return 0.0
        from api.models.wallet_history_model import WalletHistory
        rows = WalletHistory.objects.filter(
            booking_id__in=(str(obj.id), obj.id),
            tran_type="cancel_penalty",
            type="debit",
            wallet__user_type=obj.cancelled_by,
        )
        return round(sum(float(r.debit_amount or 0) for r in rows), 2)

    def get_vehicle(self, obj):
        snapshot_fields = (
            obj.vehicle_plate_number,
            obj.vehicle_brand,
            obj.vehicle_model,
            obj.vehicle_color,
            obj.vehicle_type,
        )
        if all(value is None or value == "" for value in snapshot_fields):
            return None
        vehicle_type = obj.vehicle_type
        return {
            "id": obj.rider_vehicle_id,
            "plate_number": obj.vehicle_plate_number,
            "brand": obj.vehicle_brand,
            "model": obj.vehicle_model,
            "color": obj.vehicle_color,
            "type": vehicle_type,
            "pretty_type": pretty_vehicle_type(vehicle_type),
        }
    

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