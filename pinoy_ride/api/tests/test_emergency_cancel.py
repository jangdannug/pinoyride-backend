"""US-7.3 rider emergency cancellation (backend)."""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APIClient

from api.models.booking_model import Booking
from api.models.emergency_cancel_request_model import EmergencyCancelRequest
from api.models.wallet_history_model import WalletHistory
from api.repositories.booking_repository import BookingRepository
from api.services import push_service
from api.utils.custom_error import ValidationError

from .test_advance_booking_eta import Base, _eta

DEFER = "api.services.push_service.defer"


@patch("api.services.google_maps_service.GoogleMapsService.get_eta", _eta)
class EmergencyCancelTests(Base):
    def _accepted(self, minutes_to_pickup=90):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        accepted_at = timezone.now() - timedelta(minutes=10)
        # This established acceptance has passed the newly scoped five-minute grace.
        Booking.objects.filter(id=b.id).update(accepted_at=accepted_at)
        b.accepted_at = accepted_at
        # Explicitly moved pickup for this test's two-hour cancellation scenario.
        b.scheduled_pickup_at = accepted_at + timedelta(minutes=minutes_to_pickup)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=b.scheduled_pickup_at)
        return b

    def _debits(self):
        return WalletHistory.objects.filter(tran_type="cancel_penalty", type="debit",
                                            wallet__user_type="rider", wallet__user_id=self.rider.id)

    def _request(self):
        b = self._accepted()
        self.svc.cancel_emergency_by_rider(self.rider, b.id, reason="Motorbike broke down")
        return b, EmergencyCancelRequest.objects.get(booking_id=b.id)

    def test_preview_emergency_available(self):
        b = self._accepted(90)
        self.assertTrue(self.svc.cancel_by_rider(self.rider, b.id, preview=True)["emergency_available"])
        b2 = self._accepted(300)
        self.assertFalse(self.svc.cancel_by_rider(self.rider, b2.id, preview=True)["emergency_available"])

    def test_emergency_success_releases_without_penalty(self):
        b = self._accepted()
        with patch(DEFER) as defer:
            r = self.svc.cancel_emergency_by_rider(self.rider, b.id, reason="Accident")
        b.refresh_from_db()
        self.assertEqual((b.status, b.rider_id, b.cancelled_by), (4, self.rider.id, "rider"))
        new = Booking.objects.get(id=r["new_booking_id"])
        self.assertEqual(b.replaced_by_id, new.id)
        self.assertEqual((new.status, new.rider_id), (5, None))
        self.assertNotEqual(new.ref_code, b.ref_code)
        self.assertIsNotNone(new.returned_to_pool_at)
        self.assertEqual(r["emergency_status"], "pending")
        self.assertGreater(r["penalty_amount"], 0)
        self.assertEqual(self._debits().count(), 0)
        req = EmergencyCancelRequest.objects.get(id=r["request_id"])
        self.assertEqual(req.penalty_amount, r["penalty_amount"])
        fns = [c.args[0] for c in defer.call_args_list]
        self.assertIn(push_service.notify_advance_available, fns)
        self.assertEqual(len(fns), 2)  # passenger push + pool re-offer

    def test_free_case_rejected(self):
        b = self._accepted(300)
        with self.assertRaisesMessage(ValidationError, "Use regular cancel"):
            self.svc.cancel_emergency_by_rider(self.rider, b.id, reason="Accident")
        self.assertFalse(EmergencyCancelRequest.objects.exists())

    def test_reason_required(self):
        b = self._accepted()
        for reason in (None, "", "   "):
            with self.assertRaises(ValidationError):
                self.svc.cancel_emergency_by_rider(self.rider, b.id, reason=reason)

    def test_endpoint(self):
        b = self._accepted()
        res = APIClient().post("/api/booking/cancel_emergency_rider/",
                               {"rider_id": self.rider.id, "booking_id": b.id, "reason": "Flat tire"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        res = APIClient().post("/api/booking/cancel_emergency_rider/",
                               {"rider_id": self.rider.id, "booking_id": b.id}, format="json")
        self.assertNotEqual(res.status_code, 200)

    def test_list_filter(self):
        _, req = self._request()
        _, req2 = self._request()
        self.svc.decide_emergency(req2.id, "approve")
        pending = self.svc.list_emergency_requests()
        self.assertEqual([x["id"] for x in pending["items"]], [req.id])
        row = pending["items"][0]
        for k in ("ref_code", "booking_id", "rider_id", "rider_name", "rider_mobile", "reason",
                  "scheduled_pickup_at", "cancelled_at", "penalty_amount", "status", "admin_reason", "reviewed_at"):
            self.assertIn(k, row)
        self.assertEqual([x["id"] for x in self.svc.list_emergency_requests("approved")["items"]], [req2.id])
        self.assertEqual(self.svc.list_emergency_requests("all")["total"], 2)

    def test_approve_no_debit(self):
        _, req = self._request()
        r = self.svc.decide_emergency(req.id, "approve")
        self.assertEqual(r["status"], "approved")
        self.assertEqual(self._debits().count(), 0)

    def test_reject_debits_and_adds_violation(self):
        _, req = self._request()
        r = self.svc.decide_emergency(req.id, "reject", reason="No proof")
        self.assertEqual(r["status"], "rejected")
        self.assertEqual(self._debits().count(), 1)
        self.assertAlmostEqual(float(self._debits().first().debit_amount), req.penalty_amount)
        self.assertEqual(r["violation_total"], 1)

    def test_double_decide(self):
        _, req = self._request()
        self.svc.decide_emergency(req.id, "approve")
        with self.assertRaises(ValidationError):
            self.svc.decide_emergency(req.id, "reject", reason="x")

    def test_reject_requires_reason(self):
        _, req = self._request()
        with self.assertRaises(ValidationError):
            self.svc.decide_emergency(req.id, "reject")
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

    def test_push_sent_on_decision(self):
        _, req = self._request()
        with patch(DEFER) as defer:
            self.svc.decide_emergency(req.id, "reject", reason="No proof")
        defer.assert_called_once()
        self.assertIs(defer.call_args.args[0], push_service.notify_rider_emergency_decision)
        req.refresh_from_db()
        res = push_service.notify_rider_emergency_decision(req)   # log mode
        self.assertEqual(res["title"], "Emergency cancellation rejected")
        self.assertIn(req.booking.ref_code, res["body"])
        self.assertIn("₱", res["body"])
        self.assertIn("No proof", res["body"])
        self.assertEqual(res["data"]["type"], "emergency_cancel_decision")
        self.assertEqual(res["data"]["booking_id"], str(req.booking_id))

    def test_history_and_details_fields(self):
        b, req = self._request()
        row = next(x for x in BookingRepository.get_rider_booking_history(self.rider.id, page_size=20)["bookings"]
                   if x["id"] == b.id)
        self.assertEqual((row["is_emergency"], row["emergency_status"]), (True, "pending"))
        self.assertEqual(row["emergency_penalty_amount"], req.penalty_amount)
        self.svc.decide_emergency(req.id, "reject", reason="No proof")
        row = next(x for x in BookingRepository.get_rider_booking_history(self.rider.id, page_size=20)["bookings"]
                   if x["id"] == b.id)
        self.assertEqual((row["emergency_status"], row["emergency_admin_reason"]), ("rejected", "No proof"))
        self.assertIsNotNone(row["emergency_reviewed_at"])
        res = APIClient().post("/api/booking/get_details/", {"booking_id": b.id, "rider_id": self.rider.id},
                               format="json")
        data = res.json().get("data") or {}
        self.assertEqual(data.get("emergency_status"), "rejected")
        b.refresh_from_db()
        d = self.svc.details(self.rider2, b.replaced_by_id)  # new booking: no emergency history
        self.assertFalse(d["is_emergency"])

    def test_regular_cancel_not_emergency(self):
        b = self._accepted()
        self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        row = next(x for x in BookingRepository.get_rider_booking_history(self.rider.id, page_size=20)["bookings"]
                   if x["id"] == b.id)
        self.assertFalse(row["is_emergency"])
        self.assertIsNone(row["emergency_status"])


@patch("api.services.google_maps_service.GoogleMapsService.get_eta", _eta)
class RepoolNewBookingTests(Base):
    """Mark, Oct 23 2026: every rider cancel re-pools under a NEW booking / ref_code."""

    def _accepted(self, minutes_to_pickup=90):
        b = self._booking(hours=3)
        self.svc.accept(self.rider, b.id)
        accepted_at = timezone.now() - timedelta(minutes=10)
        # This established acceptance has passed the newly scoped five-minute grace.
        Booking.objects.filter(id=b.id).update(accepted_at=accepted_at)
        b.accepted_at = accepted_at
        # Explicitly moved pickup for this test's two-hour cancellation scenario.
        b.scheduled_pickup_at = accepted_at + timedelta(minutes=minutes_to_pickup)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=b.scheduled_pickup_at)
        return b

    def _check_split(self, b, r):
        b.refresh_from_db()
        new = Booking.objects.get(id=r["new_booking_id"])
        self.assertEqual((b.status, b.cancelled_by, b.rider_id, b.replaced_by_id), (4, "rider", self.rider.id, new.id))
        self.assertIsNotNone(b.cancelled_at)
        self.assertEqual((new.status, new.rider_id, new.accepted_at, new.vehicle_plate_number), (5, None, None, None))
        self.assertEqual(r["new_ref_code"], new.ref_code)
        self.assertNotEqual(new.ref_code, b.ref_code)
        for f in ("customer_id", "pickup_location", "dropoff_location", "scheduled_pickup_at", "booking_type",
                  "payment_type", "is_advance", "window_start", "window_end"):
            self.assertEqual(getattr(new, f), getattr(b, f), f)
        self.assertEqual(new.booking_payment.first().total_amount, b.booking_payment.first().total_amount)
        return new

    def _rider_debits(self, booking_id=None):
        qs = WalletHistory.objects.filter(tran_type="cancel_penalty", type="debit", wallet__user_type="rider")
        return qs.filter(booking_id=str(booking_id)) if booking_id else qs

    def test_free_cancel_new_booking(self):
        b = self._accepted(300)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        self.assertFalse(r["penalty_applies"])
        self._check_split(b, r)

    def test_penalty_cancel_new_booking_penalty_on_old(self):
        b = self._accepted(90)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        new = self._check_split(b, r)
        self.assertEqual(self._rider_debits(b.id).count(), 1)
        self.assertEqual(self._rider_debits(new.id).count(), 0)

    def test_emergency_new_booking_and_reject_charges_old_only(self):
        b = self._accepted(90)
        r = self.svc.cancel_emergency_by_rider(self.rider, b.id, reason="Accident")
        new = self._check_split(b, r)
        self.assertEqual(EmergencyCancelRequest.objects.get(id=r["request_id"]).booking_id, b.id)
        # Same rider re-accepts the new booking, then Cancel Anyway: no double penalty on one booking.
        second_acceptance = self.svc.accept(self.rider, new.id)
        # Cancel Anyway on the later acceptance, after its own (grace-free) interval.
        second_acceptance.accepted_at = timezone.now() - timedelta(minutes=10)
        Booking.objects.filter(id=new.id).update(accepted_at=second_acceptance.accepted_at)
        self.assertFalse(self.svc.details(self.rider, new.id)["is_emergency"])
        r2 = self.svc.cancel_by_rider(self.rider, new.id, reason="again")
        self.svc.decide_emergency(r["request_id"], "reject", reason="No proof")
        self.assertEqual(self._rider_debits(b.id).count(), 1)
        self.assertEqual(self._rider_debits(new.id).count(), 1)  # its own Cancel Anyway only
        self.assertIsNotNone(r2["new_booking_id"])

    def test_passenger_history_shows_old_as_rider_cancelled_no_penalty(self):
        b = self._accepted(90)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")  # rider penalty applies
        rows = {x["id"]: x for x in BookingRepository.get_customer_booking_history(self.customer.id, page_size=50)["bookings"]}
        old = rows[b.id]
        self.assertEqual((old["status"], old["cancelled_by"], old["pretty_status"]), (4, "rider", "Cancelled"))
        self.assertEqual((old["replaced_by"], old["replaced_by_ref_code"], old["is_replaced"]),
                         (r["new_booking_id"], r["new_ref_code"], True))
        self.assertEqual(old["penalty_amount"], 0.0)
        self.assertIn(r["new_booking_id"], rows)
        cust = WalletHistory.objects.filter(tran_type="cancel_penalty", wallet__user_type="customer")
        self.assertFalse(cust.exists())
        self.assertEqual(self.svc.violation_count("customer", self.customer.id), 0)

    def test_details_returns_replaced_by(self):
        b = self._accepted(300)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        res = APIClient().post("/api/booking/get_details/", {"booking_id": b.id}, format="json")
        data = res.json()["data"]
        self.assertEqual((data["status"], data["cancelled_by"]), (4, "rider"))
        self.assertEqual((data["replaced_by"], data["replaced_by_ref_code"], data["is_replaced"]),
                         (r["new_booking_id"], r["new_ref_code"], True))
        self.assertEqual(data["penalty_amount"], 0.0)
        res = APIClient().post("/api/booking/get_details/", {"booking_id": r["new_booking_id"]}, format="json")
        data = res.json()["data"]
        self.assertEqual(data["status"], 5)
        self.assertIsNone(data["replaced_by"])
        self.assertFalse(data["is_replaced"])
        self.assertEqual((data["replaces"], data["replaces_ref_code"]), (b.id, b.ref_code))

    def test_overlap_and_open_count_freed(self):
        from api.services import booking_window_service as bws
        b = self._accepted(300)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        active = list(bws.active_bookings(self.customer.id).values_list("id", flat=True))
        self.assertNotIn(b.id, active)
        self.assertIn(r["new_booking_id"], active)
        n = Booking.objects.filter(customer_id=self.customer.id, is_advance=True, status__in=[5, 1]).count()
        self.assertEqual(n, 1)
        self.assertNotIn(b.id, [x["id"] for x in self.svc.get_upcoming(self.customer.id)["bookings"]])

    def test_rider_history_old_cancelled_new_separate(self):
        b = self._accepted(90)
        r = self.svc.cancel_emergency_by_rider(self.rider, b.id, reason="Accident")
        self.svc.accept(self.rider, r["new_booking_id"])
        rows = {x["id"]: x for x in BookingRepository.get_rider_booking_history(self.rider.id, page_size=50)["bookings"]}
        self.assertEqual(rows[b.id]["pretty_status"], "Cancelled")
        self.assertTrue(rows[b.id]["is_emergency"])
        self.assertEqual(rows[r["new_booking_id"]]["pretty_status"], "Scheduled")
        self.assertFalse(rows[r["new_booking_id"]]["is_emergency"])

    def test_new_booking_fields_promo_push_and_passenger_cancel(self):
        from api.models.promo_availed_model import PromoAvailed
        from api.services import passenger_push
        b = self._accepted(300)
        Booking.objects.filter(id=b.id).update(note_to_rider="gate 2", reminder_sent_at=timezone.now())
        pa = PromoAvailed.objects.create(customer=self.customer, booking=b)
        with patch(DEFER) as defer:
            r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        new = Booking.objects.get(id=r["new_booking_id"])
        self.assertEqual(new.note_to_rider, "gate 2")
        for f in ("reminder_sent_at", "early_reminder_sent_at", "accepted_at", "rider_arrived_at", "cancelled_at"):
            self.assertIsNone(getattr(new, f), f)
        self.assertIsNotNone(new.returned_to_pool_at)
        pa.refresh_from_db()
        self.assertEqual(pa.booking_id, new.id)
        calls = {c.args[0]: c.args[1] for c in defer.call_args_list}
        self.assertEqual(calls[passenger_push.rider_cancelled_reassigning].id, new.id)
        # expire_stale / at-risk only touch status 5, so the old (status 4) row is left alone
        Booking.objects.filter(id__in=[b.id, new.id]).update(scheduled_pickup_at=timezone.now() - timedelta(minutes=1))
        self.svc.expire_stale(self.customer.id)
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by), (4, "rider"))
        Booking.objects.filter(id=new.id).update(status=5, cancelled_by=None,
                                                 scheduled_pickup_at=timezone.now() + timedelta(hours=5))
        res = self.svc.cancel_by_customer(self.customer.id, new.id, reason="changed plans")
        self.assertEqual(res["status"], 4)

    def test_new_booking_in_pool_for_any_rider(self):
        b = self._accepted(300)
        r = self.svc.cancel_by_rider(self.rider, b.id, reason="flat tire")
        pool = [x["id"] for x in self.svc.advance_pending(self.rider2)["bookings"]]
        self.assertIn(r["new_booking_id"], pool)
        self.assertNotIn(b.id, pool)
        self.svc.accept(self.rider2, r["new_booking_id"])
