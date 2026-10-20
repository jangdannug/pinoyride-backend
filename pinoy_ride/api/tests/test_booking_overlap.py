"""Booking overlap policy, passenger + shared parts (QA overlap-test-cases OV-01..OV-24, OV-50..52).
Google Maps is mocked: every ride is 30 minutes unless a test says otherwise."""
import json
import threading
from datetime import timedelta
from unittest.mock import patch

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.customer_model import Customer
from api.services import booking_window_service as bws
from api.services.advance_booking_service import AdvanceBookingService
from api.utils.custom_error import ValidationError

PICK_LAT, PICK_LNG = "14.5530", "121.0213"     # Greenbelt 5
DROP_LAT, DROP_LNG = "14.5509", "121.0503"     # BGC
MAPS = "api.services.google_maps_service.GoogleMapsService.get_eta"
PAYMENT = {"base_amount": 70.30, "tip": 0, "promo_discount": 0, "rider_net_amount": 74.69, "total_amount": 87.87,
           "total_amount_wo_promo": 87.87, "minimum_fare": 40, "pesos_per_km": 10, "distance_km_round": 3,
           "booking_fee": 0, "commission": 13.18}


def maps(minutes=30, traffic=None, fallback=False):
    res = {"duration_minutes": minutes, "distance_km": 3.2, "status": "OK", "using_fallback": fallback}
    if traffic is not None:
        res["duration_in_traffic_minutes"] = traffic
    return lambda *a, **k: dict(res)


def slot(hours=3):
    """A pickup time well past the 2-hour lead rule, on a whole minute (the "4:30 PM" of the examples)."""
    return (timezone.now() + timedelta(hours=hours)).replace(second=0, microsecond=0)


class WindowMathTests(TestCase):
    def test_advance_window_is_pickup_plus_duration(self):
        t = slot()
        w = bws.build_window(t, 30, is_advance=True)
        self.assertEqual((w.start, w.end, w.est_duration_minutes), (t, t + timedelta(minutes=30), 30))

    def test_regular_window_adds_max_wait(self):
        t = timezone.now()
        w = bws.build_window(t, 30, is_advance=False)
        self.assertEqual(w.end, t + timedelta(minutes=45))

    @override_settings(PASSENGER_BUFFER_MINUTES=5, REGULAR_MAX_WAIT_MINUTES=10)   # OV-51: config, no code change
    def test_buffer_and_wait_are_configurable(self):
        t = slot()
        self.assertEqual(bws.build_window(t, 30, True).end, t + timedelta(minutes=35))
        self.assertEqual(bws.build_window(t, 30, False).end, t + timedelta(minutes=45))

    def test_overlap_rule_examples_1_to_4(self):
        a = slot()                                     # 4:30-5:00
        a_end = a + timedelta(minutes=30)
        for offset, expected in ((15, True), (25, True), (30, False), (-30, False), (-20, True)):
            s = a + timedelta(minutes=offset)          # 4:45, 4:55, 5:00, 4:00, 4:10
            self.assertEqual(bws.overlaps(a, a_end, s, s + timedelta(minutes=30)), expected, offset)

    def test_duration_prefers_traffic_then_duration(self):
        with patch(MAPS, side_effect=maps(30, traffic=42)):
            self.assertEqual(bws.estimate_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG), 42)
        with patch(MAPS, side_effect=maps(31)):
            self.assertEqual(bws.estimate_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG), 31)

    def test_advance_passes_departure_time(self):
        t = slot()
        with patch(MAPS, side_effect=maps(30)) as m:
            bws.compute_window(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG, True, scheduled_pickup_at=t)
        self.assertEqual(m.call_args.kwargs["departure_time"], int(t.timestamp()))

    def test_fallback_uses_distance_and_fallback_speed(self):
        expected = bws.fallback_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG)   # ~3.1 km / 20 km/h
        self.assertEqual(expected, 10)
        with patch(MAPS, side_effect=maps(6, fallback=True)):
            self.assertEqual(bws.estimate_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG), expected)
        with patch(MAPS, side_effect=RuntimeError("down")):
            self.assertEqual(bws.estimate_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG), expected)
        with override_settings(WINDOW_FALLBACK_SPEED_KMH=40):
            self.assertEqual(bws.fallback_duration_minutes(PICK_LAT, PICK_LNG, DROP_LAT, DROP_LNG), 5)


class ApiBase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(fname="Pat", lname="Passenger", mobile="639170000999")
        self.client = APIClient()
        p = patch(MAPS, side_effect=maps(30))
        p.start()
        self.addCleanup(p.stop)

    def create(self, at=None, **extra):
        data = {"customer_id": self.customer.id, "booking_type": "1", "payment_type": "cash",
                "pickup_location": "Greenbelt 5", "pickup_lat": PICK_LAT, "pickup_long": PICK_LNG,
                "dropoff_location": "BGC", "dropoff_lat": DROP_LAT, "dropoff_long": DROP_LNG,
                "payment_details": json.dumps(PAYMENT), "all_payment_details": json.dumps(PAYMENT)}
        if at is not None:
            data.update({"is_advance": "1", "scheduled_pickup_at": at.isoformat()})
        data.update(extra)
        return self.client.post("/api/booking/create/", data, format="json")

    def ok(self, r):
        self.assertEqual(r.status_code, 200, r.content)
        return Booking.objects.get(id=r.data["data"]["id"])

    def rejected(self, r, message=bws.OVERLAP_MESSAGE):
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data["message"], message)

    def booking(self, status, advance, start, minutes=30, rider=None):
        w = bws.build_window(start, minutes, advance)
        b = Booking.objects.create(customer=self.customer, booking_type="1", pickup_location="A", dropoff_location="B",
                                   pickup_lat=PICK_LAT, pickup_long=PICK_LNG, dropoff_lat=DROP_LAT,
                                   dropoff_long=DROP_LNG, payment_type="cash", status=status, is_advance=advance,
                                   scheduled_pickup_at=start if advance else None, window_start=w.start,
                                   window_end=w.end, est_duration_minutes=minutes)
        BookingPayment.objects.create(booking=b, minimum_fare=50, pesos_per_km=10, distance_km_round=3,
                                      booking_fee=20, total_amount=100, commission=10)
        return b


class PassengerOverlapTests(ApiBase):
    def test_ov01_first_advance_accepted_and_window_saved(self):
        t = slot()
        b = self.ok(self.create(t))
        self.assertEqual((b.window_start, b.window_end, b.est_duration_minutes), (t, t + timedelta(minutes=30), 30))
        self.assertEqual(b.status, 5)

    def test_ov02_to_ov06_examples(self):
        t = slot()
        self.ok(self.create(t))                                     # 4:30-5:00
        self.rejected(self.create(t + timedelta(minutes=15)))       # OV-02 4:45
        self.rejected(self.create(t + timedelta(minutes=25)))       # OV-03 4:55
        self.rejected(self.create(t - timedelta(minutes=20)))       # OV-06 4:10-4:40
        self.ok(self.create(t + timedelta(minutes=30)))             # OV-04 5:00 adjacent
        self.ok(self.create(t - timedelta(minutes=30)))             # OV-05 4:00-4:30

    def test_ov07_regular_overlapping_upcoming_advance_rejected(self):
        # Advance pickup in 20 minutes (booked earlier); regular now needs 30 + 15 min wait.
        self.booking(5, True, timezone.now() + timedelta(minutes=20))
        self.rejected(self.create())

    def test_ov08_regular_with_far_advance_accepted(self):
        self.booking(5, True, slot(hours=5))
        b = self.ok(self.create())
        self.assertFalse(b.is_advance)
        self.assertEqual(b.est_duration_minutes, 30)
        self.assertAlmostEqual((b.window_end - b.window_start).total_seconds(), 45 * 60, delta=1)

    def test_ov09_advance_overlapping_active_regular_rejected(self):
        # A long regular trip (3 h) that is under way.
        self.booking(2, False, timezone.now(), minutes=180)
        self.rejected(self.create(slot(hours=2) + timedelta(minutes=30)))

    def test_ov09_active_regular_running_long_still_counts_until_now(self):
        b = self.booking(2, False, timezone.now() - timedelta(hours=5))   # estimate ended long ago
        w = bws.window_for_booking(b)
        self.assertGreaterEqual(w.end, timezone.now() - timedelta(seconds=5))

    def test_ov10_second_regular_rejected_on_server(self):
        for status in (0, 1, 2):                                    # searching, accepted, started
            with self.subTest(status=status):
                b = self.booking(status, False, timezone.now() - timedelta(hours=2))
                self.rejected(self.create(), bws.ONGOING_MESSAGE)
                b.delete()

    def test_ov10_regular_while_advance_trip_under_way_rejected(self):
        self.booking(1, True, timezone.now() - timedelta(minutes=5))
        self.rejected(self.create(), bws.ONGOING_MESSAGE)

    def test_ov11_regular_after_completed_regular_accepted(self):
        self.booking(3, False, timezone.now() - timedelta(minutes=10))
        self.ok(self.create())

    def test_ov12_excluded_statuses(self):
        t = slot()
        for status in (3, 4):                                       # completed, cancelled/rejected
            with self.subTest(status=status):
                b = self.booking(status, True, t)
                self.ok(self.create(t)).delete()
                b.delete()

    def test_ov12_expired_advance_excluded(self):
        # Unaccepted advance whose pickup passed but whose stored window still overlaps: expire_stale runs first.
        t = slot()
        old = self.booking(5, True, timezone.now() - timedelta(minutes=1))
        Booking.objects.filter(id=old.id).update(window_start=t, window_end=t + timedelta(minutes=30))
        self.ok(self.create(t))
        old.refresh_from_db()
        self.assertEqual((old.status, old.cancelled_by), (4, "system"))

    def test_ov14_past_pickup_rejected(self):
        r = self.create(timezone.now() - timedelta(hours=1))
        self.assertEqual(r.status_code, 400)

    def test_ov15_lead_and_max_days_still_apply(self):
        self.assertEqual(self.create(timezone.now() + timedelta(minutes=90)).status_code, 400)
        self.assertEqual(self.create(timezone.now() + timedelta(days=31)).status_code, 400)

    def test_ov16_three_open_advance_limit_still_applies(self):
        for h in (3, 5, 7):
            self.ok(self.create(slot(hours=h)))
        r = self.create(slot(hours=9))
        self.assertEqual(r.status_code, 400)
        self.assertIn("at most 3", r.data["message"])

    def test_ov50_legacy_booking_without_stored_window_still_checked(self):
        t = slot()
        b = self.booking(5, True, t)
        Booking.objects.filter(id=b.id).update(window_start=None, window_end=None, est_duration_minutes=None)
        # Fallback duration ~10 min: 4:30-4:40 blocks 4:35, not 4:40.
        self.rejected(self.create(t + timedelta(minutes=5)))
        self.ok(self.create(t + timedelta(minutes=10)))

    def test_ov13_create_locks_customer_row(self):
        table = Customer._meta.db_table
        with CaptureQueriesContext(connection) as ctx:
            self.ok(self.create(slot()))
        self.assertTrue(any("FOR UPDATE" in q["sql"] and table in q["sql"] for q in ctx.captured_queries))


class ModificationTests(ApiBase):
    """No reschedule endpoint exists today; retry() is the path that revalidates a changed booking."""
    svc = AdvanceBookingService()

    def move(self, b, at):
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=at)
        return self.svc.retry(self.customer.id, b.id)

    def test_ov20_move_into_other_booking_rejected(self):
        t = slot()
        self.booking(5, True, t)
        b = self.booking(5, True, slot(hours=5))
        with self.assertRaisesMessage(ValidationError, bws.OVERLAP_MESSAGE):
            self.move(b, t + timedelta(minutes=15))

    def test_ov21_overlapping_only_itself_accepted(self):
        t = slot()
        a = self.booking(5, True, t)
        a = self.move(a, t + timedelta(minutes=10))
        self.assertEqual(a.window_start, t + timedelta(minutes=10))

    def test_ov22_move_to_adjacent_accepted(self):
        t = slot()
        self.booking(5, True, t)
        b = self.move(self.booking(5, True, slot(hours=5)), t + timedelta(minutes=30))
        self.assertEqual(b.window_end, t + timedelta(minutes=60))

    def test_ov24_duration_change_recomputed_and_rechecked(self):
        t = slot()
        b = self.booking(5, True, t)
        self.booking(5, True, t + timedelta(minutes=40))
        with patch(MAPS, side_effect=maps(30, traffic=50)):          # route now takes 50 min
            with self.assertRaisesMessage(ValidationError, bws.OVERLAP_MESSAGE):
                self.svc.retry(self.customer.id, b.id)
        with patch(MAPS, side_effect=maps(35)):
            b = self.svc.retry(self.customer.id, b.id)
        self.assertEqual((b.est_duration_minutes, b.window_end), (35, t + timedelta(minutes=35)))

    def test_retry_regular_while_another_regular_active_rejected(self):
        self.booking(1, False, timezone.now())
        stale = self.booking(4, False, timezone.now() - timedelta(minutes=5))   # timed out, no canceller
        with self.assertRaisesMessage(ValidationError, bws.ONGOING_MESSAGE):
            self.svc.retry(self.customer.id, stale.id)


class ConcurrentCreateTests(TransactionTestCase):
    """OV-13: two overlapping creates at the same moment -> exactly one succeeds (real Postgres row lock)."""

    def test_parallel_overlapping_creates(self):
        customer = Customer.objects.create(fname="Pat", lname="Passenger", mobile="639170000998")
        t = slot()
        barrier = threading.Barrier(2)
        results = []
        orig_lock = bws.lock_customer

        def slow_lock(cid):
            row = orig_lock(cid)
            threading.Event().wait(0.3)      # hold the lock so the other request has to wait for it
            return row

        def worker(minutes):
            try:
                barrier.wait()
                r = APIClient().post("/api/booking/create/", {
                    "customer_id": customer.id, "booking_type": "1", "payment_type": "cash",
                    "pickup_location": "Greenbelt 5", "pickup_lat": PICK_LAT, "pickup_long": PICK_LNG,
                    "dropoff_location": "BGC", "dropoff_lat": DROP_LAT, "dropoff_long": DROP_LNG,
                    "payment_details": json.dumps(PAYMENT), "all_payment_details": json.dumps(PAYMENT),
                    "is_advance": "1", "scheduled_pickup_at": (t + timedelta(minutes=minutes)).isoformat(),
                }, format="json")
                results.append((r.status_code, r.data.get("message")))
            finally:
                connections.close_all()

        with patch(MAPS, side_effect=maps(30)), patch.object(bws, "lock_customer", side_effect=slow_lock):
            threads = [threading.Thread(target=worker, args=(m,)) for m in (0, 10)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(30)
        self.assertEqual(sorted(code for code, _ in results), [200, 400], results)
        self.assertIn(bws.OVERLAP_MESSAGE, [m for _, m in results])
        self.assertEqual(Booking.objects.filter(customer=customer).count(), 1)
