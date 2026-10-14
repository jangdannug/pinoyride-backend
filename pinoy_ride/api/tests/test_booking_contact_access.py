from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models.booking_contact_session_model import BookingContactSession
from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.customer_model import Customer
from api.models.rider_model import Rider
from api.serializers.booking_serializer import BookingSerializer
from api.services.booking_contact_service import BookingContactService


class BookingContactAccessTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            fname="Pat", lname="Passenger", mobile="639170000999"
        )
        self.other = Customer.objects.create(
            fname="Other", lname="User", mobile="639170000111"
        )
        self.rider = Rider.objects.create(
            first_name="R",
            last_name="X",
            mobile_no="639170000888",
            is_verified=1,
            status=1,
        )
        self.booking = Booking.objects.create(
            customer=self.customer,
            rider=self.rider,
            booking_type="1",
            pickup_location="A",
            dropoff_location="B",
            pickup_lat="14.5",
            pickup_long="120.9",
            dropoff_lat="14.5",
            dropoff_long="120.9",
            payment_type="cash",
            status=3,
            completed_at=timezone.now() - timedelta(hours=1),
        )
        BookingPayment.objects.create(
            booking=self.booking,
            minimum_fare=50,
            pesos_per_km=10,
            distance_km_round=3,
            booking_fee=20,
            total_amount=100,
            commission=10,
        )
        BookingContactService().provision_for_booking(self.booking)

    def test_history_payload_omits_real_phones(self):
        data = BookingSerializer(
            self.booking, context={"omit_contact_phone": True}
        ).data
        self.assertNotIn("mobile_no", data.get("rider_details") or {})
        ekyc = (data.get("rider_details") or {}).get("ekyc_details") or {}
        self.assertNotIn("pretty_mobile_no", ekyc)
        self.assertNotIn("mobile", data.get("customer") or {})

    def test_customer_get_contact_returns_proxy_only(self):
        payload = BookingContactService().get_contact_payload(
            self.booking.id, "customer", self.customer.id
        )
        self.assertEqual(payload["access_status"], "active")
        self.assertTrue(payload["proxy_contact_number"].startswith("+63"))
        self.assertNotIn("639170000888", payload["proxy_contact_number"])

    def test_wrong_customer_gets_404(self):
        with self.assertRaises(Exception):
            BookingContactService().get_contact_payload(
                self.booking.id, "customer", self.other.id
            )

    def test_expired_contact_denied(self):
        Booking.objects.filter(id=self.booking.id).update(
            completed_at=timezone.now() - timedelta(hours=25)
        )
        session = BookingContactSession.objects.get(booking_id=self.booking.id)
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save(update_fields=["expires_at"])
        from api.utils.custom_error import ForbiddenError

        with self.assertRaises(ForbiddenError):
            BookingContactService().get_contact_payload(
                self.booking.id, "customer", self.customer.id
            )

    @patch("api.services.booking_contact_service.BookingContactService.get_contact_payload")
    def test_get_contact_endpoint(self, mock_payload):
        mock_payload.return_value = {
            "proxy_contact_number": "+63 917 800 0001",
            "dial_uri": "tel:+639178000001",
            "expires_at": timezone.now().isoformat(),
            "access_status": "active",
        }
        client = APIClient()
        r = client.post(
            "/api/booking/get_contact/",
            {
                "booking_id": self.booking.id,
                "user_type": "customer",
                "customer_id": self.customer.id,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
