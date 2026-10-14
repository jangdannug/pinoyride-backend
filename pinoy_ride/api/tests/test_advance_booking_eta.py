from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.customer_model import Customer
from api.models.pinoy_ride_wallet_model import PinoyRideWallet
from api.models.rider_model import Rider
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.models.wallet_history_model import WalletHistory
from api.models.wallet_model import Wallet
from api.repositories.booking_repository import BookingRepository
from api.serializers.booking_serializer import BookingSerializer
from api.services.advance_booking_service import AdvanceBookingService, ConflictError
from api.utils.custom_error import NotFoundError, ValidationError

LAT, LNG = "14.53507", "120.98216"
FAR_LAT = "14.65"  # ~13 km north


def _eta(*a, **k):
    return {"duration_minutes": 7, "duration_in_traffic_minutes": 8, "distance_km": 2.5}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.svc = AdvanceBookingService()
        self.customer = Customer.objects.create(fname="Pat", lname="Passenger", mobile="639170000999")
        self.rider = self._rider("639170000888")
        self.rider2 = self._rider("639170000777")
        self.vehicle = self._vehicle(self.rider, "1", "MOTO 1")
        self._vehicle(self.rider2, "1", "MOTO 2")
        for uid, ut in ((self.customer.id, "customer"), (self.rider.id, "rider"), (self.rider2.id, "rider")):
            Wallet.objects.create(user_id=uid, user_type=ut, type="user-wallet")
        PinoyRideWallet.objects.create(user_id=1, user_type="pinoy_ride", type="pinoy-ride-wallet")

    def _rider(self, mobile):
        return Rider.objects.create(first_name="R", last_name="X", mobile_no=mobile, is_verified=1, status=1,
                                    current_lat=LAT, current_long=LNG,
                                    current_location_updated_at=timezone.now())

    def _vehicle(self, rider, t, plate):
        return RiderVehicleDetails.objects.create(rider=rider, v_type=t, v_brand="B", v_model="M", v_color="Red",
                                                  v_plate_number=plate, status=1, is_current=True)

    def _booking(self, hours=3, btype="1", status=5, total=100.0, advance=True, lat=LAT):
        b = Booking.objects.create(customer=self.customer, booking_type=btype, pickup_location="A",
                                   dropoff_location="B", pickup_lat=lat, pickup_long=LNG, dropoff_lat=LAT,
                                   dropoff_long=LNG, payment_type="cash", status=status, is_advance=advance,
                                   scheduled_pickup_at=(timezone.now() + timedelta(hours=hours)) if advance else None)
        BookingPayment.objects.create(booking=b, minimum_fare=50, pesos_per_km=10, distance_km_round=3,
                                      booking_fee=20, total_amount=total, commission=10)
        return b


class CreateWindowTests(Base):
    def test_window(self):
        now = timezone.now()
        with self.assertRaises(ValidationError):
            self.svc.parse_scheduled_pickup((now + timedelta(minutes=119)).isoformat())
        self.svc.parse_scheduled_pickup((now + timedelta(minutes=121)).isoformat())
        self.svc.parse_scheduled_pickup((now + timedelta(days=29, hours=23)).isoformat())
        with self.assertRaises(ValidationError):
            self.svc.parse_scheduled_pickup((now + timedelta(days=30, minutes=1)).isoformat())
        with self.assertRaises(ValidationError):
            self.svc.parse_scheduled_pickup("2030-01-01T10:00:00")  # naive
        with self.assertRaises(ValidationError):
            self.svc.parse_scheduled_pickup((now - timedelta(hours=1)).isoformat())

    def test_max_open_per_customer(self):
        for _ in range(3):
            self._booking()
        with self.assertRaises(ValidationError):
            self.svc.check_customer_can_book_advance(self.customer.id)

    def test_mark_as_advance_and_serializer(self):
        b = self._booking(status=0, advance=False)
        self.svc.mark_as_advance(b, timezone.now() + timedelta(hours=3))
        data = BookingSerializer(b).data
        self.assertEqual(data["status"], 5)
        self.assertEqual(data["pretty_status"], "Scheduled")
        self.assertEqual(data["booking_label"], "Advance Booking")
        self.assertTrue(data["scheduled_pickup_at"].endswith("+08:00"))


class PoolAcceptTests(Base):
    @patch("api.services.google_maps_service.GoogleMapsService.get_eta", _eta)
    def test_scheduled_not_in_instant_pending(self):
        self._booking()
        res = BookingRepository.pending_list(LAT, LNG, "1", rider_id=self.rider.id)
        self.assertEqual(res["bookings"], [])

    def test_advance_pending_filters(self):
        ok = self._booking()
        self._booking(btype="2")
        self._booking(lat=FAR_LAT)
        past = self._booking()
        Booking.objects.filter(id=past.id).update(scheduled_pickup_at=timezone.now() - timedelta(minutes=1))
        ids = [b["id"] for b in self.svc.advance_pending(self.rider, LAT, LNG)["bookings"]]
        self.assertEqual(ids, [ok.id])

    def test_no_current_vehicle(self):
        RiderVehicleDetails.objects.filter(rider=self.rider).update(is_current=False, v_type="2")
        RiderVehicleDetails.objects.create(rider=self.rider, v_type="1", v_brand="B", v_model="M", v_color="C",
                                           v_plate_number="X 1", status=1)
        with self.assertRaises(ValidationError):
            self.svc.advance_pending(self.rider, LAT, LNG)

    def test_accept_rules(self):
        car = self._booking(btype="2")
        with self.assertRaises(ValidationError):
            self.svc.accept(self.rider, car.id)
        b = self._booking()
        accepted = self.svc.accept(self.rider, b.id)
        self.assertEqual(accepted.status, 5)
        self.assertEqual(accepted.vehicle_plate_number, "MOTO 1")
        self.assertIsNotNone(accepted.accepted_at)
        with self.assertRaises(ConflictError):
            self.svc.accept(self.rider2, b.id)
        # scheduled accept is not an ongoing booking
        self.assertIsNone(BookingRepository.check_rider_ongoing_booking(self.rider.id))
        # gap rule
        near = self._booking(hours=3.5)
        with self.assertRaises(ValidationError):
            self.svc.accept(self.rider, near.id)

    def test_details_phone_visibility(self):
        b = self._booking()
        d = self.svc.details(self.rider, b.id)
        self.assertIsNone(d["passenger_mobile"])
        self.assertEqual(d["title"], "Advance Booking")
        self.assertEqual(d["distance_fare"] + d["minimum_fare"] + d["booking_fee"], 100.0)
        self.svc.accept(self.rider, b.id)
        self.assertEqual(self.svc.details(self.rider, b.id)["passenger_mobile"], "639170000999")
        with self.assertRaises(NotFoundError):
            self.svc.details(self.rider2, b.id)


class StartArrivedTests(Base):
    def test_start_window(self):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        with self.assertRaises(ValidationError):
            self.svc.start(self.rider, b.id)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=59))
        self.assertEqual(self.svc.start(self.rider, b.id).status, 1)

    def test_arrived(self):
        b = self._booking(status=1, advance=False)
        Booking.objects.filter(id=b.id).update(rider=self.rider)
        with self.assertRaises(NotFoundError):
            self.svc.arrived(self.rider2, b.id, LAT, LNG)
        with self.assertRaises(ValidationError):
            self.svc.arrived(self.rider, b.id, FAR_LAT, LNG)
        self.svc.arrived(self.rider, b.id, LAT, LNG)
        with self.assertRaises(ValidationError):
            self.svc.arrived(self.rider, b.id, LAT, LNG)
        eta = self.svc.get_eta(b.id, customer_id=self.customer.id)
        self.assertEqual(eta["eta_state"], "arrived")
        b.refresh_from_db()
        self.assertTrue(BookingSerializer(b).data["arrived"])

    def test_arrived_requires_status_1(self):
        b = self._booking()
        self.svc.accept(self.rider, b.id)
        with self.assertRaises(ValidationError):
            self.svc.arrived(self.rider, b.id, LAT, LNG)


class CancelTests(Base):
    def test_customer_no_penalty_over_2h(self):
        b = self._booking(hours=3)
        r = self.svc.cancel_by_customer(self.customer.id, b.id)
        self.assertFalse(r["penalty_applies"])
        self.assertEqual(r["status"], 4)

    def test_customer_penalty_and_preview(self):
        b = self._booking(hours=3)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=20))
        p = self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)
        self.assertEqual(p["penalty_amount"], 10.0)
        b.refresh_from_db()
        self.assertEqual(b.status, 5)
        r = self.svc.cancel_by_customer(self.customer.id, b.id, reason="x")
        self.assertEqual(r["violation_added"], 1)
        self.assertEqual(WalletHistory.objects.filter(tran_type="cancel_penalty").count(), 1)
        w = Wallet.objects.get(user_id=self.customer.id, user_type="customer")
        self.assertEqual(w.avail_balance, -10.0)
        self.assertEqual(PinoyRideWallet.objects.get(user_id=1).avail_balance, 10.0)
        b.refresh_from_db()
        self.assertEqual(BookingSerializer(b).data["penalty_amount"], 10.0)

    @override_settings(CANCEL_PENALTY_PERCENT=20)
    def test_settings_override(self):
        b = self._booking(hours=3)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=90))
        self.assertEqual(self.svc.cancel_by_customer(self.customer.id, b.id, preview=True)["penalty_amount"], 20.0)

    def test_rider_no_penalty_over_2h_before_pickup(self):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        preview = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire", preview=True)
        self.assertFalse(preview["penalty_applies"])
        self.assertEqual(preview["penalty_amount"], 0.0)

    def test_rider_cancel_releases_and_flags(self):
        flagged = False
        for i in range(3):
            b = self._booking(hours=3 + i * 2)
            Booking.objects.filter(id=b.id).update(
                scheduled_pickup_at=timezone.now() + timedelta(minutes=90),
            )
            self.svc.accept(self.rider, b.id)
            r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
            b.refresh_from_db()
            self.assertEqual(b.status, 5)
            self.assertIsNone(b.rider_id)
            self.assertIsNone(b.vehicle_plate_number)
            self.assertIsNotNone(b.returned_to_pool_at)
            flagged = r["flagged_for_review"]
        self.assertTrue(flagged)
        self.assertEqual(Rider.objects.get(id=self.rider.id).status, 1)  # no auto-suspend
        self.assertEqual(self.svc.violation_count("rider", self.rider.id), 3)

    def test_rider_cannot_cancel_after_trip_started(self):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        Booking.objects.filter(id=b.id).update(
            scheduled_pickup_at=timezone.now() + timedelta(minutes=30),
        )
        self.svc.start(self.rider, b.id)
        with self.assertRaises(ValidationError):
            self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire", preview=True)
        Booking.objects.filter(id=b.id).update(status=2)
        with self.assertRaises(ValidationError):
            self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire", preview=True)

    def test_rider_cancel_shows_in_history_with_penalty(self):
        b = self._booking(hours=3)
        Booking.objects.filter(id=b.id).update(
            scheduled_pickup_at=timezone.now() + timedelta(minutes=90),
        )
        self.svc.accept(self.rider, b.id)
        self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        history = BookingRepository.get_rider_booking_history(self.rider.id, page_size=20)
        ids = [row["id"] for row in history["bookings"]]
        self.assertIn(b.id, ids)
        row = next(x for x in history["bookings"] if x["id"] == b.id)
        self.assertEqual(row["pretty_status"], "Cancelled")
        self.assertGreater(row["penalty_amount"], 0)
        b.refresh_from_db()
        customer_row = BookingSerializer(b).data
        self.assertEqual(customer_row["pretty_status"], "Returned to pool")

    def test_rider_cancel_shows_cancelled_in_history_without_penalty(self):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        preview = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire", preview=True)
        self.assertEqual(preview["penalty_amount"], 0.0)
        self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        history = BookingRepository.get_rider_booking_history(self.rider.id, page_size=20)
        row = next(x for x in history["bookings"] if x["id"] == b.id)
        self.assertEqual(row["pretty_status"], "Cancelled")
        self.assertEqual(row["penalty_amount"], 0)


class RetryTests(Base):
    def test_retry_pending_and_advance(self):
        b = self._booking(status=0, advance=False)
        self.assertEqual(self.svc.retry(self.customer.id, b.id).status, 0)
        a = self._booking(hours=3)
        self.assertEqual(self.svc.retry(self.customer.id, a.id).status, 5)
        Booking.objects.filter(id=a.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=90))
        with self.assertRaises(ValidationError):
            self.svc.retry(self.customer.id, a.id)

    def test_pooled_at_reset_by_retry(self):
        b = self._booking(status=0, advance=False)
        old = timezone.now() - timedelta(hours=1)
        Booking.objects.filter(id=b.id).update(created_at=old)
        b.refresh_from_db()
        before = BookingSerializer(b).data["pooled_at"]
        self.assertTrue(before.endswith("+08:00"))
        r = APIClient().post("/api/booking/retry/", {"booking_id": b.id, "customer_id": self.customer.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        after = r.json()["data"]["pooled_at"]
        self.assertTrue(after.endswith("+08:00"))
        self.assertGreater(after, before)

    def test_retry_blocked_when_accepted_or_cancelled(self):
        a = self._booking()
        self.svc.accept(self.rider, a.id)
        with self.assertRaises(ValidationError):
            self.svc.retry(self.customer.id, a.id)
        c = self._booking()
        self.svc.cancel_by_customer(self.customer.id, c.id)
        with self.assertRaises(ValidationError):
            self.svc.retry(self.customer.id, c.id)


class ReminderTests(Base):
    def test_once(self):
        b = self._booking()
        self.svc.accept(self.rider, b.id)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=4))
        cancelled = self._booking()
        Booking.objects.filter(id=cancelled.id).update(status=4, rider=self.rider,
                                                       scheduled_pickup_at=timezone.now() + timedelta(minutes=4))
        self.assertEqual(self.svc.send_due_reminders(), 1)
        self.assertEqual(self.svc.send_due_reminders(), 0)


class EtaTests(Base):
    def _active(self):
        b = self._booking(status=1, advance=False)
        Booking.objects.filter(id=b.id).update(rider=self.rider)
        Rider.objects.filter(id=self.rider.id).update(current_lat="14.55", current_long=LNG,
                                                      current_location_updated_at=timezone.now())
        return b

    def test_states(self):
        s = self._booking()
        self.assertEqual(self.svc.get_eta(s.id, customer_id=self.customer.id)["eta_state"], "not_started")
        with self.assertRaises(NotFoundError):
            self.svc.get_eta(s.id, customer_id=999999)
        b = self._active()
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_eta) as m:
            r = self.svc.get_eta(b.id, customer_id=self.customer.id)
            self.svc.get_eta(b.id, customer_id=self.customer.id)
            self.assertEqual(m.call_count, 1)  # cached
        self.assertEqual(r["eta_state"], "en_route")
        self.assertEqual(r["eta_minutes"], 8)
        self.assertEqual(r["refresh_after_seconds"], 30)

    def test_fallback_and_stale_and_arriving(self):
        b = self._active()
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=Exception("boom")):
            r = self.svc.get_eta(b.id, rider_id=self.rider.id)
        self.assertTrue(r["using_fallback"])
        self.assertEqual(r["eta_state"], "en_route")
        cache.clear()
        Rider.objects.filter(id=self.rider.id).update(
            current_location_updated_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(self.svc.get_eta(b.id, customer_id=self.customer.id)["eta_state"], "unavailable")
        cache.clear()
        Rider.objects.filter(id=self.rider.id).update(current_lat=LAT, current_location_updated_at=timezone.now())
        with patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_eta):
            self.assertEqual(self.svc.get_eta(b.id, customer_id=self.customer.id)["eta_state"], "arriving_now")


class AdvanceTripCompletionTests(Base):
    """Arrived advance booking goes through the existing instant-ride start/complete endpoint."""

    @patch("api.services.rider_service.RiderService.update_rider_coordinates", lambda *a, **k: None)
    def test_start_and_complete_via_existing_endpoint(self):
        Wallet.objects.filter(user_id=self.rider.id, user_type="rider").update(avail_balance=500, credit_amount=500)
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=45))
        self.svc.start(self.rider, b.id)
        self.svc.arrived(self.rider, b.id, LAT, LNG)
        c = APIClient()
        for status in ("2", "3"):
            r = c.post("/api/booking/update_status_for_rider/", {
                "rider_id": self.rider.id, "booking_id": b.id, "status": status,
                "current_lat": LAT, "current_long": LNG}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
        b.refresh_from_db()
        self.assertEqual(b.status, 3)
        self.assertEqual(Rider.objects.get(id=self.rider.id).is_available, 1)
        self.assertIsNone(BookingRepository.check_rider_ongoing_booking(self.rider.id))


class PassengerRiderInfoTests(Base):
    def test_advance_booking_rider_info_for_passenger(self):
        RiderVehicleDetails.objects.create(rider=self.rider, v_type="3", v_brand="B", v_model="M", v_color="C",
                                           v_plate_number="NEWER 3", status=1)  # newer, not current
        b = self._booking()
        self.assertFalse(BookingSerializer(b).data["rider_assigned"])
        self.svc.accept(self.rider, b.id)
        b.refresh_from_db()
        d = BookingSerializer(b).data
        self.assertTrue(d["rider_assigned"])
        self.assertEqual(d["rider_details"]["vehicle_details"][0]["plate_number"], "MOTO 1")
        self.assertEqual(d["rider_details"]["ekyc_details"]["pretty_mobile_no"], "639170000888")
        self.assertEqual(d["vehicle"]["plate_number"], "MOTO 1")


class UpcomingTests(Base):
    def test_upcoming_includes_in_progress(self):
        sched = self._booking(hours=5)
        accepted_adv = self._booking(hours=3)
        self.svc.accept(self.rider, accepted_adv.id)
        instant_1 = self._booking(status=1, advance=False)
        instant_2 = self._booking(status=2, advance=False)
        self._booking(status=0, advance=False)  # pending instant: not upcoming
        self._booking(status=3, advance=False)  # completed: not upcoming
        self._booking(status=4)  # cancelled advance: not upcoming
        ids = [b["id"] for b in self.svc.get_upcoming(self.customer.id)["bookings"]]
        self.assertEqual(ids, [instant_2.id, instant_1.id, accepted_adv.id, sched.id])


class EndpointTests(Base):
    def test_routes(self):
        c = APIClient()
        b = self._booking()
        r = c.post("/api/booking/get_eta/", {"booking_id": b.id, "customer_id": self.customer.id}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        if r.status_code == 200:
            self.assertEqual(r.json()["data"]["eta_state"], "not_started")
            r = c.post("/api/booking/accept_advance/", {"booking_id": b.id, "rider_id": self.rider.id}, format="json")
            self.assertEqual(r.status_code, 200)
            r = c.post("/api/booking/accept_advance/", {"booking_id": b.id, "rider_id": self.rider2.id}, format="json")
            self.assertEqual(r.status_code, 409)
