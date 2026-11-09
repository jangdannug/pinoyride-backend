from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.wallet_history_model import WalletHistory
from api.tests.test_advance_booking_eta import Base, _eta
from api.services import advance_booking_service as svc_mod

NOW = timezone.now()
ACCEPTED = NOW - timedelta(hours=1)


def booking(*, seconds=301, pickup=30):
    now = ACCEPTED + timedelta(seconds=seconds)
    return SimpleNamespace(id=1, rider_id=7, status=5, accepted_at=ACCEPTED,
        created_at=ACCEPTED - timedelta(minutes=20),
        scheduled_pickup_at=now + timedelta(minutes=pickup) if pickup is not None else None), now


@override_settings(CANCEL_FREE_GRACE_MINUTES=5)
@patch.object(svc_mod, '_now', lambda: NOW)
class AcceptanceGraceTests(Base):
    @patch.object(svc_mod.AdvanceBookingService, '_penalty_fare_base', lambda b: Decimal('100'))
    def test_five_minute_boundary_free_before_and_at_501_charged(self):
        for seconds, passenger, rider in ((299, (0.0, 0), (0.0, 0)), (300, (0.0, 0), (0.0, 0)),
                                          (301, (20.0, 1), (10.0, 1))):
            with self.subTest(seconds=seconds):
                b, now = booking(seconds=seconds)
                with patch.object(svc_mod, '_now', return_value=now):
                    self.assertEqual(self.svc.customer_penalty(b), passenger)
                    self.assertEqual(self.svc.rider_penalty(b), rider)

    @patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
    def test_inside_two_hours_preview_and_cancel_free_during_grace(self):
        b = self._booking(hours=3)
        b.scheduled_pickup_at = NOW + timedelta(minutes=30)
        b.save()
        self.svc.accept(self.rider, b.id)
        customer = self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)
        rider = self.svc.cancel_by_rider(self.rider, b.id, preview=True)
        self.assertEqual(customer['penalty_amount'], 0)
        self.assertFalse(customer['penalty_applies'])
        self.assertEqual(customer['violation_added'], 0)
        self.assertEqual(rider['penalty_amount'], 0)
        self.assertFalse(rider['penalty_applies'])
        self.assertEqual(rider['violation_added'], 0)
        b.refresh_from_db()
        self.assertEqual(b.status, 5)
        self.svc.cancel_by_rider(self.rider, b.id, reason='changed plans')
        self.assertEqual(WalletHistory.objects.filter(tran_type='cancel_penalty').count(), 0)

    @patch.object(svc_mod.AdvanceBookingService, '_penalty_fare_base', lambda b: Decimal('100'))
    def test_after_grace_rider_two_hour_window_still_inclusive(self):
        for minutes, passenger, rider in ((125, (0.0, 0), (0.0, 0)), (119, (20.0, 1), (10.0, 1))):
            with self.subTest(minutes=minutes):
                b, now = booking(pickup=minutes)
                with patch.object(svc_mod, '_now', return_value=now):
                    self.assertEqual(self.svc.customer_penalty(b), passenger)
                    self.assertEqual(self.svc.rider_penalty(b), rider)

    def test_unassigned_cancellation_remains_free_even_with_stale_timestamp(self):
        b, _ = booking()
        b.rider_id = None
        self.assertEqual(self.svc.customer_penalty(b), (0.0, 0))
        self.assertEqual(self.svc.rider_penalty(b), (0.0, 0))

    @patch.object(svc_mod.AdvanceBookingService, '_penalty_fare_base', lambda b: Decimal('100'))
    def test_no_acceptance_does_not_fall_back_to_booking_creation(self):
        # Once a rider is assigned, a missing or stale imported acceptance must not grant a grace.
        b, _ = booking()
        self.assertEqual(self.svc.customer_penalty(b), (20.0, 1))
        self.assertEqual(self.svc.rider_penalty(b), (10.0, 1))
        b.accepted_at = None
        self.assertEqual(self.svc.customer_penalty(b), (20.0, 1))
        self.assertEqual(self.svc.rider_penalty(b), (10.0, 1))

    def test_no_show_remains_free_after_grace(self):
        b, _ = booking(pickup=-30)
        self.assertTrue(self.svc.is_rider_no_show(b))
        self.assertEqual(self.svc.customer_penalty(b), (0.0, 0))
        self.assertEqual(self.svc.rider_penalty(b), (0.0, 0))

    @patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
    def test_quoted_99_10_other_total_889_20_passenger_19_82_rider_9_91(self):
        b = self.svc.accept(self.rider, self._booking(hours=3, total=889.20).id)
        payment = BookingPayment.objects.get(booking=b)
        payment.all_payment_details = {'estimated_total_amount': 99.10}
        payment.save(update_fields=['all_payment_details'])
        now = b.accepted_at + timedelta(minutes=10)
        b.scheduled_pickup_at = now + timedelta(minutes=30)
        with patch.object(svc_mod, '_now', return_value=now):
            self.assertEqual(self.svc.customer_penalty(b), (19.82, 1))
            self.assertEqual(self.svc.rider_penalty(b), (9.91, 1))

    @patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
    def test_quoted_149_15_passenger_29_83_rider_half_up_14_92(self):
        b = self.svc.accept(self.rider, self._booking(hours=3, total=149.15).id)
        now = b.accepted_at + timedelta(minutes=10)
        b.scheduled_pickup_at = now + timedelta(minutes=30)
        with patch.object(svc_mod, '_now', return_value=now):
            self.assertEqual(self.svc.customer_penalty(b), (29.83, 1))
            self.assertEqual(self.svc.rider_penalty(b), (14.92, 1))

    @patch('api.services.google_maps_service.GoogleMapsService.get_eta', _eta)
    def test_repool_has_no_acceptance_then_new_acceptance_gets_fresh_grace(self):
        b = self.svc.accept(self.rider, self._booking(hours=3, total=100.0).id)
        b.scheduled_pickup_at = NOW + timedelta(minutes=90)
        b.save()
        new = self.svc._release_to_pool(self.rider, b, 'changed plans')
        self.assertIsNone(new.accepted_at)
        self.assertIsNone(new.rider_id)
        self.assertEqual(self.svc.customer_penalty(new), (0.0, 0))
        self.assertEqual(self.svc.rider_penalty(new), (0.0, 0))
        b.refresh_from_db()
        self.assertIsNotNone(b.cancelled_at)
        self.assertIsNotNone(b.accepted_at)  # preserve historical acceptance audit
        again = self.svc.accept(self.rider2, new.id)
        with patch.object(svc_mod, '_now', return_value=again.accepted_at + timedelta(minutes=4)):
            self.assertEqual(self.svc.customer_penalty(again), (0.0, 0))
            self.assertEqual(self.svc.rider_penalty(again), (0.0, 0))
        again.scheduled_pickup_at = again.accepted_at + timedelta(minutes=35, seconds=1, microseconds=1)
        with patch.object(svc_mod, '_now', return_value=again.accepted_at + timedelta(minutes=5, seconds=1)):
            self.assertEqual(self.svc.customer_penalty(again), (20.0, 1))
            self.assertEqual(self.svc.rider_penalty(again), (10.0, 1))
