"""Both apps read the role cancel-penalty percents from responses they already call."""
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from api.models.booking_model import Booking
from api.serializers.booking_serializer import BookingSerializer
from api.tests.test_advance_booking_eta import Base, _eta

DEFAULT_POLICY = {"passenger_cancel_penalty_percent": 20, "rider_cancel_penalty_percent": 10}


@patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
class CancellationPolicyPayloadTests(Base):
    def _accepted(self, pickup_minutes=30):
        b = self.svc.accept(self.rider, self._booking(hours=3).id)
        Booking.objects.filter(id=b.id).update(
            scheduled_pickup_at=timezone.now() + timedelta(minutes=pickup_minutes),
            accepted_at=timezone.now() - timedelta(minutes=10))
        return b

    def test_passenger_cancel_preview_and_result_carry_policy(self):
        b = self._accepted()
        preview = self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)
        self.assertEqual(preview["cancellation_policy"], DEFAULT_POLICY)
        result = self.svc.cancel_by_customer(self.customer.id, b.id, reason="changed plans")
        self.assertEqual(result["cancellation_policy"], DEFAULT_POLICY)

    def test_rider_cancel_preview_and_details_carry_policy(self):
        b = self._accepted()
        self.assertEqual(self.svc.details(self.rider, b.id)["cancellation_policy"], DEFAULT_POLICY)
        preview = self.svc.cancel_by_rider(self.rider, b.id, preview=True)
        self.assertEqual(preview["cancellation_policy"], DEFAULT_POLICY)
        result = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        self.assertEqual(result["cancellation_policy"], DEFAULT_POLICY)

    def test_booking_payload_carries_policy_even_when_free(self):
        b = self._booking(hours=3)
        self.assertEqual(BookingSerializer(b).data["cancellation_policy"], DEFAULT_POLICY)
        preview = self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)
        self.assertFalse(preview["penalty_applies"])
        self.assertEqual(preview["cancellation_policy"], DEFAULT_POLICY)

    @override_settings(PASSENGER_CANCEL_PENALTY_PERCENT=25, RIDER_CANCEL_PENALTY_PERCENT=15)
    def test_setting_overrides_flow_through_every_payload(self):
        want = {"passenger_cancel_penalty_percent": 25, "rider_cancel_penalty_percent": 15}
        b = self._accepted()
        self.assertEqual(BookingSerializer(b).data["cancellation_policy"], want)
        self.assertEqual(self.svc.details(self.rider, b.id)["cancellation_policy"], want)
        self.assertEqual(self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)["cancellation_policy"], want)
        self.assertEqual(self.svc.cancel_by_rider(self.rider, b.id, preview=True)["cancellation_policy"], want)
        self.assertEqual(self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)["penalty_amount"], 25.0)
