"""Overlap plan section 5 (driver checks). QA cases OV-30..OV-41 and document examples 5 and 6."""
import threading
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from api.models.advance_booking_rider_release_model import AdvanceBookingRiderRelease
from api.models.booking_model import Booking
from api.models.wallet_history_model import WalletHistory
from api.repositories.booking_repository import BookingRepository
from api.services import booking_window_service as bws
from api.tests.test_advance_booking_eta import Base, LAT, LNG
from api.utils.custom_error import ValidationError

FAR = "14.60"
TRAVEL = {"min": 0}


def _travel(o_lat, o_lng, d_lat, d_lng, departure_at=None):
    try:
        same = abs(float(o_lat) - float(d_lat)) < 1e-6 and abs(float(o_lng) - float(d_lng)) < 1e-6
    except (TypeError, ValueError):
        return 0
    return 0 if same else TRAVEL["min"]


def _maps(*a, **k):
    return {"duration_minutes": 30, "duration_in_traffic_minutes": 30, "distance_km": 5}


class RiderBase(Base):
    def setUp(self):
        super().setUp()
        from api.models.rider_model import Rider
        Rider.objects.update(is_online=1)
        self.rider.refresh_from_db()
        TRAVEL["min"] = 0
        p1 = patch.object(bws, "travel_minutes", side_effect=_travel)
        p2 = patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_maps)
        self.push = patch("api.services.push_service.defer")
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)
        self.defer = self.push.start()
        self.addCleanup(self.push.stop)

    def adv(self, minutes, ride=30, rider=None, drop=FAR):
        b = self._booking(hours=minutes / 60.0)
        Booking.objects.filter(id=b.id).update(est_duration_minutes=ride, dropoff_lat=drop, rider=rider)
        b.refresh_from_db()
        return b

    def regular(self, ride=30, status=0, rider=None):
        b = self._booking(advance=False, status=status)
        Booking.objects.filter(id=b.id).update(est_duration_minutes=ride, dropoff_lat=FAR, rider=rider)
        b.refresh_from_db()
        return b


class AdvanceAcceptTests(RiderBase):
    def test_ov30_no_assignments(self):
        self.assertEqual(self.svc.accept(self.rider, self.adv(180).id).rider_id, self.rider.id)

    def test_ov31_two_advance_overlapping(self):
        TRAVEL["min"] = 10
        self.adv(180, rider=self.rider)                      # 3:00, ride 30 -> ends 3:30
        b = self.adv(210)                                    # 3:30: 3:30 + 5 + 10 > 3:30
        with self.assertRaises(ValidationError) as e:
            self.svc.accept(self.rider, b.id)
        self.assertEqual(str(e.exception), bws.RIDER_CONFLICT_MESSAGE)
        b.refresh_from_db()
        self.assertIsNone(b.rider_id)                         # stays open for other riders
        self.assertEqual(self.svc.accept(self.rider2, b.id).rider_id, self.rider2.id)

    def test_ov31_earlier_new_booking_checked_too(self):
        TRAVEL["min"] = 10
        self.adv(210, rider=self.rider)
        with self.assertRaises(ValidationError):
            self.svc.accept(self.rider, self.adv(180).id)

    def test_ov41_sixty_minutes_apart_fits(self):
        TRAVEL["min"] = 10
        self.adv(180, rider=self.rider)
        self.assertEqual(self.svc.accept(self.rider, self.adv(240).id).rider_id, self.rider.id)

    def test_ov38_cancelled_or_done_excluded(self):
        TRAVEL["min"] = 10
        old = self.adv(180, rider=self.rider)
        Booking.objects.filter(id=old.id).update(status=4)
        self.assertEqual(self.svc.accept(self.rider, self.adv(200).id).rider_id, self.rider.id)


class RegularAcceptTests(RiderBase):
    def _accept(self, b):
        return BookingRepository.accept_booking(b, self.rider)

    def _frozen(self, minutes):
        """Advance pickup exactly `minutes` after a frozen 'now' (exact-fit cases)."""
        now = timezone.now()
        p = patch.object(bws, "_now", return_value=now)
        p.start()
        self.addCleanup(p.stop)
        b = self.adv(minutes, rider=self.rider)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=now + timedelta(minutes=minutes))

    def test_example5_ten_minutes_late_blocked(self):
        TRAVEL["min"] = 10
        self.adv(30, rider=self.rider)                       # advance pickup at 4:30
        b = self.regular(ride=30)                            # ride 4:00-4:30, +5 +10 -> 4:45
        with self.assertRaises(ValidationError) as e:
            self._accept(b)
        self.assertEqual(str(e.exception), bws.RIDER_LATE_MESSAGE)
        b.refresh_from_db()
        self.assertIsNone(b.rider_id)

    def test_example6_ten_minutes_spare_allowed(self):
        TRAVEL["min"] = 15
        self.adv(60, rider=self.rider)                       # ends 4:30 + 5 + 15 = 4:50 <= 5:00
        self.assertEqual(self._accept(self.regular(ride=30)).rider_id, self.rider.id)

    def test_exact_fit_and_ov34(self):
        TRAVEL["min"] = 15
        self._frozen(50)                   # 30 + 5 + 15 = exactly 50
        self.assertIsNotNone(self._accept(self.regular(ride=30)))

    def test_ov34_ends_before_pickup_but_buffer_makes_late(self):
        TRAVEL["min"] = 15
        self._frozen(49)
        with self.assertRaises(ValidationError):
            self._accept(self.regular(ride=30))

    def test_ov36_grace(self):
        TRAVEL["min"] = 15
        self._frozen(49)
        with override_settings(RIDER_GRACE_MINUTES=1):
            self.assertIsNotNone(self._accept(self.regular(ride=30)))

    def test_rider_already_on_a_ride(self):
        self.regular(status=1, rider=self.rider)
        with self.assertRaises(ValidationError) as e:
            self._accept(self.regular())
        self.assertEqual(str(e.exception), bws.RIDER_ONGOING_MESSAGE)

    def test_pending_list_hides_infeasible(self):
        TRAVEL["min"] = 10
        self.adv(30, rider=self.rider)
        b = self.regular(ride=30)
        ids = lambda rid: [x["id"] for x in BookingRepository.pending_list(LAT, LNG, "1", rider_id=rid)["bookings"]]
        self.assertNotIn(b.id, ids(self.rider.id))
        self.assertIn(b.id, ids(self.rider2.id))


class AtRiskTests(RiderBase):
    def _on_ride(self):
        return self.regular(status=2, rider=self.rider)        # started, drop-off is FAR

    def test_ov35_flag_then_return_to_pool(self):
        TRAVEL["min"] = 30
        self._on_ride()
        b = self.adv(50, rider=self.rider)
        Booking.objects.filter(id=b.id).update(early_reminder_sent_at=timezone.now(), accepted_at=timezone.now())
        self.assertEqual(bws.flag_at_risk_and_reassign(), (1, 0))
        b.refresh_from_db()
        self.assertIsNotNone(b.at_risk_at)
        self.assertEqual(b.rider_id, self.rider.id)
        # 25 minutes before pickup: still at risk -> back to the pool, no penalty
        later = timezone.now() + timedelta(minutes=25)
        with patch.object(bws, "_now", return_value=later):
            self.assertEqual(bws.flag_at_risk_and_reassign(now=later), (0, 1))
        b.refresh_from_db()
        self.assertIsNone(b.rider_id)
        self.assertEqual(b.status, 5)
        self.assertIsNone(b.early_reminder_sent_at)
        self.assertIsNone(b.reminder_sent_at)
        self.assertIsNone(b.at_risk_at)
        self.assertIsNotNone(b.returned_to_pool_at)
        self.assertTrue(AdvanceBookingRiderRelease.objects.filter(booking_id=b.id, rider_id=self.rider.id).exists())
        self.assertFalse(WalletHistory.objects.filter(tran_type="cancel_penalty").exists())
        self.defer.assert_not_called()                          # no new pushes

    def test_recovered_clears_flag(self):
        TRAVEL["min"] = 30
        self._on_ride()
        b = self.adv(50, rider=self.rider)
        bws.flag_at_risk_and_reassign()
        TRAVEL["min"] = 1
        bws.flag_at_risk_and_reassign()
        b.refresh_from_db()
        self.assertIsNone(b.at_risk_at)
        self.assertEqual(b.rider_id, self.rider.id)

    def test_not_on_ride_not_flagged(self):
        TRAVEL["min"] = 30
        b = self.adv(20, rider=self.rider)
        self.assertEqual(bws.flag_at_risk_and_reassign(), (0, 0))

    def test_ov37_offline_rider_returned(self):
        self.rider.is_online = 0
        self.rider.save()
        b = self.adv(20, rider=self.rider)
        self.assertEqual(bws.flag_at_risk_and_reassign()[1], 1)
        b.refresh_from_db()
        self.assertIsNone(b.rider_id)

    def test_ov23_recheck_after_time_change(self):
        TRAVEL["min"] = 10
        self.adv(180, rider=self.rider)
        b = self.adv(240, rider=self.rider)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=200))
        b.refresh_from_db()
        bws.recheck_rider_assignment(b)
        b.refresh_from_db()
        self.assertIsNone(b.rider_id)


class _TxBase(TransactionTestCase):
    """Same helpers as RiderBase, but real commits so two threads can race on row locks."""
    svc = None


for _name in ("_rider", "_vehicle", "_booking"):
    setattr(_TxBase, _name, Base.__dict__[_name])
for _name in ("adv", "regular"):
    setattr(_TxBase, _name, RiderBase.__dict__[_name])


def _tx_setup(self):
    Base.setUp(self)  # sets self.svc, customer, riders, vehicles, wallets
    TRAVEL["min"] = 0
    for p in (patch.object(bws, "travel_minutes", side_effect=_travel),
              patch("api.services.google_maps_service.GoogleMapsService.get_eta", side_effect=_maps),
              patch("api.services.push_service.defer")):
        p.start()
        self.addCleanup(p.stop)


_TxBase.setUp = _tx_setup


class ParallelAcceptTests(_TxBase):
    """OV-39: two accepts for the same rider at the same moment -> only one succeeds."""

    def test_two_regular_accepts_same_rider(self):
        b1, b2 = self.regular(), self.regular()
        results, barrier = [], threading.Barrier(2)

        def go(b):
            try:
                barrier.wait()
                results.append(BookingRepository.accept_booking(b, self.rider) is not None)
            except ValidationError:
                results.append(False)
            finally:
                connection.close()

        ts = [threading.Thread(target=go, args=(b,)) for b in (b1, b2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(Booking.objects.filter(rider=self.rider, status=1).count(), 1)

    def test_two_advance_accepts_same_rider(self):
        TRAVEL["min"] = 10
        b1, b2 = self.adv(180), self.adv(190)
        results, barrier = [], threading.Barrier(2)

        def go(b):
            try:
                barrier.wait()
                self.svc.accept(self.rider, b.id)
                results.append(True)
            except ValidationError:
                results.append(False)
            finally:
                connection.close()

        ts = [threading.Thread(target=go, args=(b,)) for b in (b1, b2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results), [False, True])
