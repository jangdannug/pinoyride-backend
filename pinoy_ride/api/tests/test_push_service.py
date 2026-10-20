"""push_service (log/fcm/disabled modes) and the rider push triggers."""
import json
import os
import sys
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.customer_model import Customer
from api.models.pinoy_ride_wallet_model import PinoyRideWallet
from api.models.rider_model import Rider
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.models.wallet_model import Wallet
from api.services import push_service
from api.services.advance_booking_service import AdvanceBookingService

PICK_LAT, PICK_LNG = "14.5530", "121.0213"  # Greenbelt 5


def push_lines(cm):
    return [m for m in cm.output if "PUSH[" in m]


def payloads(cm):
    out = []
    for m in push_lines(cm):
        if "data=" in m:
            to = m.split("to=")[1].split(" ")[0]
            out.append((to, json.loads(m.split("data=", 1)[1])))
    return out


@patch.dict(os.environ, {"PUSH_TEST_MODE": "log"})
class PushTestBase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(fname="Pat", lname="Passenger", mobile="639170000999")
        Wallet.objects.create(user_id=self.customer.id, user_type="customer", type="user-wallet")
        PinoyRideWallet.objects.create(user_id=1, user_type="pinoy_ride", type="pinoy-ride-wallet")

    def rider(self, name, lat="14.5560", lng=PICK_LNG, v_type="1", online=1, available=1, token="tok",
              verified=1, login=1):
        r = Rider.objects.create(first_name=name, last_name="R", mobile_no=f"6391700{Rider.objects.count():05d}",
                                 is_verified=verified, status=1, is_login=login, is_online=online, is_available=available,
                                 current_lat=lat, current_long=lng,
                                 firebase_token=(f"{token}-{name}-0123456789" if token else None))
        Wallet.objects.create(user_id=r.id, user_type="rider", type="user-wallet")
        RiderVehicleDetails.objects.create(rider=r, v_type=v_type, v_brand="B", v_model="M", v_color="Red",
                                           v_plate_number=f"P{r.id}", status=1, is_current=True)
        return r

    def booking(self, status=0, advance=False, rider=None, hours=3, btype="1", total=87.87):
        b = Booking.objects.create(customer=self.customer, rider=rider, booking_type=btype,
                                   pickup_location="Greenbelt 5\nMakati", dropoff_location="BGC High Street",
                                   pickup_lat=PICK_LAT, pickup_long=PICK_LNG, dropoff_lat="14.5509",
                                   dropoff_long="121.0503", payment_type="cash", status=status, is_advance=advance,
                                   scheduled_pickup_at=(timezone.now() + timedelta(hours=hours)) if advance else None)
        BookingPayment.objects.create(booking=b, minimum_fare=40, pesos_per_km=10, distance_km_round=3,
                                      booking_fee=0, total_amount=total, commission=13.18)
        return b


class PushServiceModeTests(PushTestBase):
    def test_log_mode_is_default_and_payload_is_strings(self):
        r = self.rider("A")
        b = self.booking()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PUSH_TEST_MODE", None)
            with self.assertLogs("myapp", "INFO") as cm:
                res = push_service.send_to_rider(r, "new_booking", b, title="T", body="B", eta_minutes=6)
        self.assertEqual(res["status"], "logged")
        self.assertTrue(res.delivered)
        self.assertEqual(res["data"], {"type": "new_booking", "booking_id": str(b.id), "is_advance": "false",
                                       "status": "0", "eta_minutes": "6"})
        line = push_lines(cm)[0]
        self.assertIn(f"to=rider:{r.id}", line)
        self.assertNotIn(r.firebase_token, line)  # token masked
        self.assertIn("token=…456789", line)

    def test_log_mode_logs_even_without_token(self):
        r = self.rider("A", token=None)
        with self.assertLogs("myapp", "INFO") as cm:
            res = push_service.send_to_rider(r.id, "advance_reminder", self.booking(status=5, advance=True))
        self.assertEqual(res["status"], "logged")
        self.assertIn("token=none", push_lines(cm)[0])

    def test_customer_helper_and_missing_recipient(self):
        b = self.booking()
        res = push_service.send_to_customer(self.customer.id, "rider_accepted", b, title="x", body="y")
        self.assertEqual(res["recipient"], f"customer:{self.customer.id}")
        self.assertEqual(push_service.send_to_rider(999999, "new_booking", b)["status"], "skipped")

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "disabled"})
    def test_disabled_mode(self):
        self.assertEqual(push_service.send_to_rider(self.rider("A"), "new_booking", self.booking())["status"],
                         "disabled")

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_fcm_without_token_skips(self):
        res = push_service.send_to_rider(self.rider("A", token=None), "new_booking", self.booking())
        self.assertEqual((res["status"], res["reason"]), ("skipped", "no_token"))

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm", "FIREBASE_CREDENTIALS_PATH": "/nonexistent.json"})
    def test_fcm_missing_package_or_credentials_never_raises(self):
        push_service._fcm_app = None
        with patch.dict(sys.modules, {"firebase_admin": None}):
            res = push_service.send_to_rider(self.rider("A"), "new_booking", self.booking())
        self.assertEqual(res["status"], "failed")
        self.assertIn("firebase-admin is not installed", res["reason"])

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_fcm_success(self):
        r = self.rider("A")
        with patch.object(push_service, "_fcm_send", return_value="projects/x/messages/1") as send:
            res = push_service.send_to_rider(r, "new_booking", self.booking(), title="T", body="B")
        self.assertEqual(res["status"], "sent")
        token, title, body, data = send.call_args[0]
        self.assertEqual((token, title, body, data["type"]), (r.firebase_token, "T", "B", "new_booking"))
        self.assertTrue(all(isinstance(v, str) for v in data.values()))

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_fcm_invalid_token_is_cleared(self):
        r = self.rider("A")
        with patch.object(push_service, "_fcm_send", side_effect=RuntimeError("Requested entity was not found")), \
                patch.object(push_service, "_is_bad_token_error", return_value=True):
            res = push_service.send_to_rider(r, "new_booking", self.booking())
        self.assertEqual((res["status"], res["reason"]), ("failed", "invalid_token"))
        r.refresh_from_db()
        self.assertIsNone(r.firebase_token)

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_fcm_other_error_keeps_token(self):
        r = self.rider("A")
        with patch.object(push_service, "_fcm_send", side_effect=RuntimeError("quota")):
            res = push_service.send_to_rider(r, "new_booking", self.booking())
        self.assertEqual(res["status"], "failed")
        r.refresh_from_db()
        self.assertIsNotNone(r.firebase_token)


class RiderTriggerTests(PushTestBase):
    def test_new_booking_via_create_api_goes_to_matching_nearby_online_riders(self):
        near = self.rider("Near")                                 # ~0.33 km, moto, online, free
        self.rider("Car", v_type="2")                             # wrong vehicle type
        self.rider("Offline", online=0)
        self.rider("Busy", available=2)                           # on a trip
        self.rider("Far", lat="14.5980")                          # ~5 km (> RIDER_RADIUS_KM 1.5)
        self.rider("Edge", lat="14.5674")                         # ~1.6 km (QA PN-16d)
        self.rider("Unverified", verified=0)                      # QA PN-16e
        payment = {"base_amount": 70.30, "tip": 0, "promo_discount": 0, "rider_net_amount": 74.69, "total_amount": 87.87, "total_amount_wo_promo": 87.87, "minimum_fare": 40,
                   "pesos_per_km": 10, "distance_km_round": 3, "booking_fee": 0, "commission": 13.18}
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            r = APIClient().post("/api/booking/create/", {
                "customer_id": self.customer.id, "booking_type": "1", "payment_type": "cash",
                "pickup_location": "Greenbelt 5", "pickup_lat": PICK_LAT, "pickup_long": PICK_LNG,
                "dropoff_location": "BGC", "dropoff_lat": "14.5509", "dropoff_long": "121.0503",
                "payment_details": json.dumps(payment), "all_payment_details": json.dumps(payment),
            }, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        sent = payloads(cm)
        self.assertEqual([to for to, _ in sent], [f"rider:{near.id}"])
        data = sent[0][1]
        self.assertEqual((data["type"], data["status"], data["is_advance"]), ("new_booking", "0", "false"))
        line = [m for m in push_lines(cm) if "data=" in m][0]
        self.assertIn("₱87.87", line)
        self.assertIn("🚗 New Booking Nearby!", line)
        self.assertIn("Pickup: Greenbelt 5", line)                # R1.1-c pickup + booking type
        self.assertTrue(any("eligible_riders=1 delivered=1" in m for m in cm.output))

    def test_advance_available_on_create_includes_busy_but_not_offline(self):
        near = self.rider("Near")
        busy = self.rider("Busy", available=2)
        mid = self.rider("Mid", lat="14.5980")                    # ~5 km, inside ADVANCE_RIDER_RADIUS_KM 10
        self.rider("Offline", online=0)
        self.rider("TooFar", lat="14.6500")                       # ~10.8 km
        b = self.booking(status=0)
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            AdvanceBookingService.mark_as_advance(b, timezone.now() + timedelta(hours=3))
        sent = payloads(cm)
        self.assertEqual(sorted(to for to, _ in sent), sorted(f"rider:{x.id}" for x in (near, busy, mid)))
        self.assertTrue(all(d["type"] == "advance_available" and d["status"] == "5" and d["is_advance"] == "true"
                            for _, d in sent))

    def test_rider_release_reoffers_to_others_not_releasing_rider(self):
        releasing = self.rider("Rel")
        other = self.rider("Other")
        b = self.booking(status=5, advance=True, rider=releasing, hours=5)
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            AdvanceBookingService().cancel_by_rider(releasing, b.id, reason="flat tire")
        riders = [to for to, d in payloads(cm) if d["type"] == "advance_available"]
        self.assertEqual(riders, [f"rider:{other.id}"])

    def test_passenger_cancelled_instant_via_api(self):
        r = self.rider("A", available=2)
        b = self.booking(status=1, rider=r)
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            resp = APIClient().post("/api/booking/update_status_for_customer/",
                                    {"customer_id": self.customer.id, "booking_id": b.id, "status": "4"},
                                    format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        sent = payloads(cm)
        self.assertEqual(sent[0][0], f"rider:{r.id}")
        d = sent[0][1]
        self.assertEqual((d["type"], d["status"], d["cancelled_by"], d["pickup"]),
                         ("passenger_cancelled", "4", "customer", "Greenbelt 5"))

    def test_passenger_cancelled_advance(self):
        r = self.rider("A")
        b = self.booking(status=5, advance=True, rider=r, hours=5)
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            AdvanceBookingService().cancel_by_customer(self.customer.id, b.id, reason="change of plans")
        sent = payloads(cm)
        self.assertEqual(len(sent), 1)
        to, d = sent[0]
        self.assertEqual(to, f"rider:{r.id}")
        local = timezone.localtime(b.scheduled_pickup_at)
        self.assertEqual({k: d[k] for k in ("type", "booking_id", "is_advance", "status", "eta_minutes",
                                            "cancelled_by", "pickup", "scheduled_date")},
                         {"type": "passenger_cancelled", "booking_id": str(b.id), "is_advance": "true",
                          "status": "4", "eta_minutes": "", "cancelled_by": "customer", "pickup": "Greenbelt 5",
                          "scheduled_date": local.strftime("%d %b %Y")})
        line = [m for m in push_lines(cm) if "data=" in m][0]
        self.assertIn("🚫 Advance Booking Cancelled", line)       # R1.5-b: pickup, date, time in body
        self.assertIn(local.strftime("%I:%M %p").lstrip("0"), line)

    def test_cancel_unassigned_sends_nothing_to_riders(self):
        b = self.booking(status=5, advance=True, hours=5)
        with patch.object(push_service, "send_to_rider") as send, self.assertLogs("myapp", "INFO") as cm, \
                self.captureOnCommitCallbacks(execute=True):
            AdvanceBookingService().cancel_by_customer(self.customer.id, b.id)
        send.assert_not_called()
        self.assertTrue(any(f"passenger_cancelled booking={b.id}: no assigned rider, nothing to send" in m
                            for m in cm.output))                  # QA PN-25

    def test_booking_expired_without_rider_is_skipped(self):
        b = self.booking(status=5, advance=True, hours=3)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() - timedelta(minutes=1))
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(AdvanceBookingService.expire_stale(), 1)
        cust = [(to, d) for to, d in payloads(cm) if to.startswith("customer:")]
        self.assertEqual(len(cust), 1)
        self.assertEqual(cust[0][1]["type"], "advance_expired")
        self.assertTrue(any(f"booking_expired booking={b.id}: no assigned rider" in m for m in cm.output))
        b.refresh_from_db()
        self.assertEqual((b.status, b.cancelled_by), (4, "system"))

    def test_booking_expired_with_rider_helper(self):
        r = self.rider("A")
        b = self.booking(status=4, advance=True, rider=r)
        res = push_service.notify_booking_expired(b)
        self.assertEqual((res["status"], res["data"]["type"]), ("logged", "booking_expired"))

    def test_advance_reminder_marks_sent_in_log_mode(self):
        r = self.rider("A")
        b = self.booking(status=5, advance=True, rider=r)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=4))
        with self.assertLogs("myapp", "INFO") as cm:
            self.assertEqual(AdvanceBookingService.send_due_reminders(), 1)
        to, data = payloads(cm)[0]
        self.assertEqual((to, data["type"], data["status"], data["minutes_to_pickup"]),
                         (f"rider:{r.id}", "advance_reminder", "5", "5"))
        b.refresh_from_db()
        self.assertIsNotNone(b.reminder_sent_at)
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)  # only once

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_advance_reminder_not_marked_when_not_delivered(self):
        r = self.rider("A", token=None)
        b = self.booking(status=5, advance=True, rider=r)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=4))
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)
        b.refresh_from_db()
        self.assertIsNone(b.reminder_sent_at)
        Rider.objects.filter(id=r.id).update(firebase_token="tok-later-0123456789")
        with patch.object(push_service, "_fcm_send", return_value="m1"):
            self.assertEqual(AdvanceBookingService.send_due_reminders(), 1)
        b.refresh_from_db()
        self.assertIsNotNone(b.reminder_sent_at)

    def test_advance_early_reminder_says_1_hour_in_log_mode(self):
        r = self.rider("A")
        b = self.booking(status=5, advance=True, rider=r)
        now = timezone.now()
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=now + timedelta(minutes=59),
                                               accepted_at=now - timedelta(hours=3))
        with self.assertLogs("myapp", "INFO") as cm:
            self.assertEqual(AdvanceBookingService.send_due_reminders(), 1)
        to, data = payloads(cm)[0]
        self.assertEqual((to, data["type"], data["status"], data["minutes_to_pickup"]),
                         (f"rider:{r.id}", "advance_reminder", "5", "60"))
        self.assertIn("will start in 1 hour.", push_lines(cm)[0])
        b.refresh_from_db()
        self.assertIsNotNone(b.early_reminder_sent_at)
        self.assertIsNone(b.reminder_sent_at)
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)  # only once
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=4))
        with self.assertLogs("myapp", "INFO") as cm:
            self.assertEqual(AdvanceBookingService.send_due_reminders(), 1)
        to, data = payloads(cm)[0]
        self.assertEqual(data["minutes_to_pickup"], "5")
        self.assertIn("will start in 5 minutes.", push_lines(cm)[0])
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)

    def test_advance_reminder_no_early_when_accepted_inside_hour(self):
        r = self.rider("A")
        b = self.booking(status=5, advance=True, rider=r)
        now = timezone.now()
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=now + timedelta(minutes=40), accepted_at=now)
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)
        b.refresh_from_db()
        self.assertIsNone(b.early_reminder_sent_at)

    @patch.dict(os.environ, {"PUSH_TEST_MODE": "fcm"})
    def test_advance_early_reminder_not_marked_when_not_delivered(self):
        r = self.rider("A", token=None)
        b = self.booking(status=5, advance=True, rider=r)
        Booking.objects.filter(id=b.id).update(scheduled_pickup_at=timezone.now() + timedelta(minutes=59),
                                               accepted_at=timezone.now() - timedelta(hours=3))
        self.assertEqual(AdvanceBookingService.send_due_reminders(), 0)
        b.refresh_from_db()
        self.assertIsNone(b.early_reminder_sent_at)
        Rider.objects.filter(id=r.id).update(firebase_token="tok-later-0123456789")
        with patch.object(push_service, "_fcm_send", return_value="m1"):
            self.assertEqual(AdvanceBookingService.send_due_reminders(), 1)
        b.refresh_from_db()
        self.assertIsNotNone(b.early_reminder_sent_at)

    def test_lead_time_text(self):
        self.assertEqual([push_service.lead_time_text(m) for m in (1, 5, 60, 90, 120)],
                         ["1 minute", "5 minutes", "1 hour", "90 minutes", "2 hours"])

    def test_push_failure_never_breaks_request(self):
        self.rider("Near")
        b = self.booking(status=0)
        with patch.object(push_service, "eligible_riders", side_effect=RuntimeError("boom")):
            self.assertEqual(push_service.notify_new_booking(b), [])


class PassengerHelperTests(PushTestBase):
    def test_build_payload_named_extras(self):
        b = self.booking()
        d = push_service.build_payload("rider_arrived", b, rider_name="Juan D", vehicle="Red Honda Click",
                                       plate="ABC 123", scheduled_at=None, nested={"x": 1})
        self.assertEqual((d["rider_name"], d["vehicle"], d["plate"]), ("Juan D", "Red Honda Click", "ABC 123"))
        self.assertNotIn("scheduled_at", d)
        self.assertNotIn("nested", d)

    def test_arrived_has_name_vehicle_plate(self):
        r = self.rider("Juan")
        b = self.booking(status=1, rider=r)
        Booking.objects.filter(id=b.id).update(vehicle_brand="Honda", vehicle_model="Click", vehicle_color="Red",
                                               vehicle_plate_number="ABC 123")
        b.refresh_from_db()
        title, body = push_service.customer_rider_arrived_text(b)
        self.assertEqual(body, "Juan R is at your pickup point (Red Honda Click, ABC 123).")
        res = push_service.send_to_customer(self.customer, "rider_arrived", b, title=title, body=body,
                                            **push_service.customer_rider_arrived_extra(b))
        self.assertEqual((res["data"]["rider_name"], res["data"]["vehicle"], res["data"]["plate"]),
                         ("Juan R", "Red Honda Click", "ABC 123"))
        self.assertNotIn(r.mobile_no, json.dumps(res["data"]) + body)  # PN-55 no phone numbers

    def test_rider_cancelled_advance_has_date_and_time(self):
        r = self.rider("A")
        b = self.booking(status=5, advance=True, rider=r, hours=5)
        with self.assertLogs("myapp", "INFO") as cm, self.captureOnCommitCallbacks(execute=True):
            AdvanceBookingService().cancel_by_rider(r, b.id, reason="flat tire")
        cust = [(to, d) for to, d in payloads(cm) if to.startswith("customer:")]
        self.assertEqual(len(cust), 1)
        d = cust[0][1]
        local = timezone.localtime(b.scheduled_pickup_at)
        self.assertEqual((d["type"], d["status"], d["scheduled_date"], d["scheduled_time"]),
                         ("rider_cancelled_reassigning", "5", local.strftime("%d %b %Y"),
                          local.strftime("%I:%M %p").lstrip("0")))
        self.assertTrue(any("Your rider cancelled your booking" in m and "for " in m for m in push_lines(cm)))


class RiderTokenEndpointTests(PushTestBase):
    def test_token_rejected_when_rider_not_logged_in(self):
        r = self.rider("A", token=None, login=0)
        resp = APIClient().post("/api/riders/update_firebase_token/", {"rider_id": r.id, "firebase_token": "t1"},
                                format="json")
        self.assertEqual(resp.status_code, 403, resp.content)
        r.refresh_from_db()
        self.assertIsNone(r.firebase_token)

    def test_update_token_and_logout_clears(self):
        r = self.rider("A", token=None)
        other = self.rider("B", token=None)
        Rider.objects.filter(id=other.id).update(firebase_token="shared-device-token")
        c = APIClient()
        resp = c.post("/api/riders/update_firebase_token/", {"rider_id": r.id, "firebase_token": "shared-device-token"},
                      format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        r.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(r.firebase_token, "shared-device-token")
        self.assertIsNone(other.firebase_token)  # token moves with the device
        self.assertEqual(c.post("/api/riders/update_firebase_token/", {"rider_id": r.id}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/riders/update_firebase_token/", {"rider_id": 999999, "firebase_token": "x"},
                                format="json").status_code, 404)
        resp = c.post("/api/riders/logout/", {"rider_id": r.id}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        r.refresh_from_db()
        self.assertIsNone(r.firebase_token)
