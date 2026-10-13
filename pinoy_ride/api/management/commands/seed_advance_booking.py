"""
Seed an advance booking for the rider demo.

The passenger app can't create a booking less than 2 hours ahead, and the
rider's Advance list only shows bookings within 10 km of the rider. This
command creates a Scheduled (status 5) advance booking next to the rider's
location, with a full fare breakdown, so the demo doesn't depend on timing.

Usage:
    # Advance list (4.2.1): unaccepted booking ~2 km from the rider, 3 h out
    python manage.py seed_advance_booking --rider-mobile 9170000201 \
        --customer-mobile 639170000102 --minutes 180 --offset-m 2000

    # Go to Pickup / ETA / Arrived (4.3): accepted booking 50 min out,
    # pickup right at the rider's spot (within 200 m)
    python manage.py seed_advance_booking --rider-mobile 9170000201 \
        --customer-mobile 639170000102 --minutes 50 --offset-m 0 --accept

The pickup is placed --offset-m metres north of --lat/--lng. Those default to
the rider's last reported location (riders.current_lat/long, updated when the
rider app is online), or to MOA (14.5352, 120.9822) if the rider has none.
--accept assigns the booking to the rider through
AdvanceBookingService.accept(), so the vehicle snapshot is saved the same way
the app does it. The rider must have a current vehicle of --type.
"""

import datetime
import math

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from api.models.booking_model import Booking
from api.models.booking_payment_model import BookingPayment
from api.models.customer_model import Customer
from api.models.rider_model import Rider
from api.services.advance_booking_service import AdvanceBookingService

DEFAULT_LAT, DEFAULT_LNG = 14.5352, 120.9822  # SM Mall of Asia
DROPOFF = ("Rizal Park, Ermita, Manila", 14.5831, 120.9794)


def _mobile_variants(value):
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("63"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return [digits, "63" + digits, "0" + digits]


def _pick_by_mobile(qs, field, value):
    """Deterministic lookup when the same number exists in several formats:
    1) exact match on the number passed, 2) the 63-prefixed record (the format
    the apps log in with), 3) otherwise the newest record (highest id)."""
    raw = "".join(ch for ch in str(value) if ch.isdigit())
    variants = _mobile_variants(value)
    matches = qs.filter(**{f"{field}__in": variants + [raw]})
    exact = matches.filter(**{field: raw}).order_by("-id").first()
    if exact is not None:
        return exact
    with_63 = matches.filter(**{field: "63" + variants[0]}).order_by("-id").first()
    if with_63 is not None:
        return with_63
    return matches.order_by("-id").first()


def _fare(distance_km):
    """Motorcycle-style fare: matches the shape of all_payment_details the
    passenger app sends (minimum fare + km basis + exceeding km)."""
    minimum_fare, km_basis, pesos_per_km, pesos_per_km2, booking_fee = 40.0, 2, 10.0, 10.0, 0.0
    km = math.ceil(distance_km)
    base_amount = km_basis * pesos_per_km
    exceeding = max(km - km_basis, 0)
    exceeding_total = exceeding * pesos_per_km2
    total = round(minimum_fare + base_amount + exceeding_total + booking_fee, 2)
    commission = round(total * 0.15, 2)
    return {
        "minimum_fare": minimum_fare, "pesos_per_km": pesos_per_km, "booking_fee": booking_fee,
        "base_amount": base_amount, "distance_km_round": km, "total_amount": total,
        "commission": commission, "rider_net_amount": round(total - commission, 2),
        "all_payment_details": {
            "minimum_fare": minimum_fare, "km_basis": km_basis, "pesos_per_km": pesos_per_km,
            "base_amount": base_amount, "exceeding_kms": exceeding, "pesos_per_km2": pesos_per_km2,
            "exceeding_kms_total": exceeding_total, "booking_fee": booking_fee,
            "distance_km_round": km, "total_amount": total,
        },
    }


class Command(BaseCommand):
    help = "Seed a Scheduled advance booking near the rider for the demo"

    def add_arguments(self, parser):
        parser.add_argument("--rider-mobile", required=True)
        parser.add_argument("--customer-mobile", required=True)
        parser.add_argument("--minutes", type=int, default=50,
                            help="Pickup this many minutes from now (default 50)")
        parser.add_argument("--offset-m", type=float, default=0,
                            help="Pickup distance north of the rider, metres (default 0)")
        parser.add_argument("--lat", type=float, default=None)
        parser.add_argument("--lng", type=float, default=None)
        parser.add_argument("--type", default="1", help="booking_type: 1 Motorcycle, 2 Car 4, 3 Car 6")
        parser.add_argument("--accept", action="store_true",
                            help="Assign it to the rider (needed for Go to Pickup / Arrived)")

    @transaction.atomic
    def handle(self, *args, **o):
        rider = _pick_by_mobile(Rider.objects.all(), "mobile_no", o["rider_mobile"])
        if rider is None:
            raise CommandError("Rider not found. Run seed_test_accounts first.")
        customer = _pick_by_mobile(Customer.objects.all(), "mobile", o["customer_mobile"])
        if customer is None:
            raise CommandError("Customer not found. Run seed_test_accounts first.")
        self.stdout.write(f"Rider id={rider.id} ({rider.mobile_no}), customer id={customer.id} ({customer.mobile})")

        try:
            lat = o["lat"] if o["lat"] is not None else float(rider.current_lat or DEFAULT_LAT)
            lng = o["lng"] if o["lng"] is not None else float(rider.current_long or DEFAULT_LNG)
        except (TypeError, ValueError):
            lat, lng = DEFAULT_LAT, DEFAULT_LNG
        if not lat or not lng:
            lat, lng = DEFAULT_LAT, DEFAULT_LNG
        pickup_lat = lat + o["offset_m"] / 111_320.0

        now = timezone.now()
        pickup_at = now + datetime.timedelta(minutes=o["minutes"])
        dname, dlat, dlng = DROPOFF
        from geopy.distance import geodesic
        distance_km = round(geodesic((pickup_lat, lng), (dlat, dlng)).kilometers, 2)
        fare = _fare(distance_km)
        local_now = timezone.localtime(now)

        booking = Booking.objects.create(
            ref_code=f"ADVSEED{now.strftime('%Y%m%d%H%M%S%f')}",
            customer=customer,
            booking_type=str(o["type"]),
            pickup_location=f"Demo pickup ({pickup_lat:.5f}, {lng:.5f})",
            pickup_lat=f"{pickup_lat:.6f}", pickup_long=f"{lng:.6f}",
            dropoff_location=dname, dropoff_lat=str(dlat), dropoff_long=str(dlng),
            distance_km=str(distance_km), payment_type="cash",
            status=5, is_advance=True, scheduled_pickup_at=pickup_at,
            date_created=local_now.strftime("%Y-%m-%d"), time_created=local_now.strftime("%H:%M:%S"),
        )
        BookingPayment.objects.create(booking=booking, type="cash", status=0, tip=0, promo_discount=0,
                                      total_amount_wo_promo=fare["total_amount"], **fare)

        if o["accept"]:
            try:
                AdvanceBookingService().accept(rider, booking.id)
            except Exception as e:  # ValidationError / ConflictError from the service
                raise CommandError(
                    f"Could not accept for the rider: {e}. Set a current vehicle of type "
                    f"{o['type']} (Vehicles screen or Go Online picker) and try again."
                )
            booking.refresh_from_db()

        self.stdout.write(self.style.SUCCESS(
            f"Booking id={booking.id} ref={booking.ref_code} type={booking.booking_type} "
            f"pickup={timezone.localtime(pickup_at):%Y-%m-%d %H:%M %Z} "
            f"at ({pickup_lat:.6f}, {lng:.6f}), {o['offset_m']:.0f} m from ({lat:.6f}, {lng:.6f}), "
            f"total=P{fare['total_amount']:.2f}, "
            f"{'accepted by rider ' + str(rider.id) if o['accept'] else 'unaccepted (in Advance list)'}"
        ))
