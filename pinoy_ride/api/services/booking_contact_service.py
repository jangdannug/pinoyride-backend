from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from api.models import Booking, BookingContactSession, Customer, Rider
from api.utils.app_logger import app_logger
from api.utils.custom_error import ForbiddenError, NotFoundError, ValidationError
from api.utils.phone_format import normalize_ph_e164, pretty_ph_mobile, tel_uri

CONTACT_ACCESS_HOURS = 24


class BookingContactService:
    """Masked proxy contact for completed bookings (24-hour window)."""

    def provision_for_booking(self, booking: Booking) -> BookingContactSession | None:
        if int(booking.status) != 3:
            return None
        if BookingContactSession.objects.filter(booking_id=booking.id).exists():
            return BookingContactSession.objects.get(booking_id=booking.id)

        completed_at = booking.completed_at or timezone.now()
        expires_at = completed_at + timedelta(hours=CONTACT_ACCESS_HOURS)

        rider_proxy, customer_proxy, twilio_sid = self._create_proxy_pair(booking)

        return BookingContactSession.objects.create(
            booking=booking,
            twilio_session_sid=twilio_sid,
            rider_proxy_number=rider_proxy,
            customer_proxy_number=customer_proxy,
            expires_at=expires_at,
        )

    def get_contact_payload(
        self,
        booking_id: int,
        user_type: str,
        user_id: int,
    ) -> dict:
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            self._log_denied("booking_not_found", booking_id, user_type, user_id)
            raise NotFoundError("Booking not found")

        if not self._caller_owns_booking(booking, user_type, user_id):
            self._log_denied("forbidden_caller", booking_id, user_type, user_id)
            raise NotFoundError("Booking not found")

        if int(booking.status) != 3:
            self._log_denied("not_completed", booking_id, user_type, user_id)
            raise ValidationError("Contact is only available for completed bookings")

        if not booking.completed_at:
            booking.completed_at = booking.updated_at or timezone.now()
            booking.save(update_fields=["completed_at"])

        session = BookingContactSession.objects.filter(booking_id=booking.id).first()
        if not session:
            session = self.provision_for_booking(booking)
        if not session:
            raise ValidationError("Contact is not available for this booking")

        now = timezone.now()
        if now >= session.expires_at or session.closed_at:
            self._close_session(session)
            self._log_denied("expired", booking_id, user_type, user_id)
            raise ForbiddenError("Contact access expired.")

        proxy_raw = (
            session.rider_proxy_number
            if user_type == "customer"
            else session.customer_proxy_number
        )

        return {
            "proxy_contact_number": pretty_ph_mobile(proxy_raw),
            "dial_uri": tel_uri(proxy_raw),
            "expires_at": timezone.localtime(session.expires_at).isoformat(),
            "access_status": "active",
        }

    def _caller_owns_booking(self, booking: Booking, user_type: str, user_id: int) -> bool:
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return False
        if user_type == "customer":
            return booking.customer_id == uid
        if user_type == "rider":
            return booking.rider_id == uid
        return False

    def _create_proxy_pair(self, booking: Booking):
        service_sid = getattr(settings, "TWILIO_PROXY_SERVICE_SID", None) or ""
        if service_sid and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            rider_proxy, customer_proxy, twilio_sid = self._twilio_proxy_pair(
                booking, service_sid
            )
            return rider_proxy, customer_proxy, twilio_sid
        rider_proxy, customer_proxy = self._local_proxy_pair(booking.id)
        return rider_proxy, customer_proxy, None

    def _local_proxy_pair(self, booking_id: int):
        """Dev / fallback: unique synthetic proxy numbers (never real user numbers)."""
        rider_proxy = normalize_ph_e164(
            f"63917{(booking_id * 7919) % 10_000_000:07d}"
        )
        customer_proxy = normalize_ph_e164(
            f"63918{(booking_id * 9973 + 5_000_000) % 10_000_000:07d}"
        )
        if rider_proxy == customer_proxy:
            customer_proxy = normalize_ph_e164(
                f"63918{(booking_id * 9973 + 5_000_001) % 10_000_000:07d}"
            )
        return rider_proxy, customer_proxy

    def _twilio_proxy_pair(self, booking: Booking, service_sid: str):
        from twilio.rest import Client

        customer = Customer.objects.filter(id=booking.customer_id).first()
        rider = Rider.objects.filter(id=booking.rider_id).first()
        if not customer or not rider:
            r, c = self._local_proxy_pair(booking.id)
            return r, c, None

        customer_phone = normalize_ph_e164(customer.mobile)
        rider_phone = normalize_ph_e164(rider.mobile_no)
        if not customer_phone or not rider_phone:
            r, c = self._local_proxy_pair(booking.id)
            return r, c, None

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        unique = f"booking-{booking.id}-{secrets.token_hex(4)}"
        session = client.proxy.services(service_sid).sessions.create(
            unique_name=unique[:64],
            ttl=CONTACT_ACCESS_HOURS * 3600,
        )

        rider_participant = session.participants.create(
            identifier=f"+{rider_phone}",
            friendly_name=f"rider-{booking.rider_id}",
        )
        customer_participant = session.participants.create(
            identifier=f"+{customer_phone}",
            friendly_name=f"customer-{booking.customer_id}",
        )

        rider_proxy = normalize_ph_e164(
            getattr(rider_participant, "proxy_identifier", "") or ""
        )
        customer_proxy = normalize_ph_e164(
            getattr(customer_participant, "proxy_identifier", "") or ""
        )
        if not rider_proxy or not customer_proxy:
            r, c = self._local_proxy_pair(booking.id)
            return r, c, None

        return rider_proxy, customer_proxy, session.sid

    def _close_session(self, session: BookingContactSession):
        if session.closed_at:
            return
        session.closed_at = timezone.now()
        session.save(update_fields=["closed_at", "updated_at"])
        if session.twilio_session_sid and settings.TWILIO_ACCOUNT_SID:
            try:
                from twilio.rest import Client

                service_sid = getattr(settings, "TWILIO_PROXY_SERVICE_SID", None)
                if service_sid:
                    client = Client(
                        settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
                    )
                    client.proxy.services(service_sid).sessions(
                        session.twilio_session_sid
                    ).update(status="closed")
            except Exception as exc:
                app_logger(2, "Failed to close Twilio proxy session", {"error": str(exc)})

    @staticmethod
    def _log_denied(reason: str, booking_id, user_type, user_id):
        app_logger(
            2,
            "booking_contact_access_denied",
            {
                "reason": reason,
                "booking_id": booking_id,
                "user_type": user_type,
                "user_id": user_id,
            },
        )
