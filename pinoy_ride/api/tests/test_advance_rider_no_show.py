from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from api.services import advance_booking_service as svc_mod
from api.services.advance_booking_service import AdvanceBookingService, STATUS_SCHEDULED, STATUS_ACCEPTED

NOW = timezone.now()


def _b(minutes_from_now, rider_id=7, status=STATUS_SCHEDULED):
    return SimpleNamespace(rider_id=rider_id, status=status, created_at=NOW - timedelta(days=2),
                           accepted_at=NOW - timedelta(hours=1) if rider_id else None,
                           scheduled_pickup_at=NOW + timedelta(minutes=minutes_from_now))


@patch.object(svc_mod, "_now", lambda: NOW)
@patch.object(AdvanceBookingService, "_penalty_fare_base", lambda b: Decimal('200'))
class RiderNoShowTests(SimpleTestCase):
    def setUp(self):
        self.s = AdvanceBookingService.__new__(AdvanceBookingService)

    def test_30_min_past_pickup_not_started_is_free(self):
        b = _b(-30)
        self.assertTrue(self.s.is_rider_no_show(b))
        self.assertEqual(self.s.customer_penalty(b), (0.0, 0))

    def test_29_min_past_pickup_still_penalised(self):
        b = _b(-29)
        self.assertFalse(self.s.is_rider_no_show(b))
        self.assertGreater(self.s.customer_penalty(b)[0], 0)

    def test_rider_heading_to_pickup_is_not_no_show(self):
        b = _b(-60, status=STATUS_ACCEPTED)
        self.assertFalse(self.s.is_rider_no_show(b))
        self.assertGreater(self.s.customer_penalty(b)[0], 0)

    def test_no_rider_assigned_is_not_no_show(self):
        self.assertFalse(self.s.is_rider_no_show(_b(-60, rider_id=None)))

    def test_before_pickup_unchanged(self):
        self.assertFalse(self.s.is_rider_no_show(_b(10)))
        self.assertGreater(self.s.customer_penalty(_b(10))[0], 0)
        self.assertEqual(self.s.customer_penalty(_b(600)), (0.0, 0))

    def test_pending_no_rider_is_free_even_inside_2h(self):
        self.assertEqual(self.s.customer_penalty(_b(117, rider_id=None)), (0.0, 0))
        self.assertEqual(self.s.customer_penalty(_b(10, rider_id=None)), (0.0, 0))

    def test_accepted_inside_2h_still_penalised(self):
        self.assertGreater(self.s.customer_penalty(_b(117))[0], 0)

    def test_rider_no_show_cancellation_is_free_too(self):
        b = _b(-30)
        self.assertTrue(self.s.is_rider_no_show(b))
        self.assertEqual(self.s.rider_penalty(b), (0.0, 0))
