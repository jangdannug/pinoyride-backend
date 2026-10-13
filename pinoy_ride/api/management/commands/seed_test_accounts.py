"""
Temporary seeder for local rider + customer login testing.

Usage:
    python manage.py seed_test_accounts
    python manage.py seed_test_accounts --rider-mobile 9170000001 --customer-mobile 9170000002
    python manage.py seed_test_accounts --rider-mobile 9170000101 \
        --customer-mobile 9170000102 --plate-prefix WEB

Seeds everything the rider app's Vehicles screens read:
  - rider.drivers_license_no / rider.drivers_license_no_expiration_date
    (shown in the Vehicles header)
  - one vehicle per service type (1 Motorcycle, 2 Car 4 Seaters,
    3 Car 6 Seaters) with brand, model, color and a normalized unique plate;
    one vehicle per type with brand, model, color and a normalized unique plate.

Idempotent: re-running updates the same rider/customer/vehicles in place
(vehicles are matched by plate, ignoring spaces/dashes/case) and resets them
to the seeded values. Vehicle images are not seeded (media storage is S3);
the app falls back to the vehicle-type icon.
"""

import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models.customer_model import Customer
from api.models.pinoy_ride_wallet_model import PinoyRideWallet
from api.models.rider_model import Rider
from api.models.rider_vehicle_details_model import RiderVehicleDetails
from api.services.wallet_service import WalletService
from api.utils.customer_utils import CustomUtils
from api.utils.vehicle_plate_utils import (
    ALLOWED_VEHICLE_TYPES,
    normalize_plate_number,
    plate_compare_key,
)

# Fixed (not relative to today) so re-runs don't change the value.
SEED_LICENSE_EXPIRATION = datetime.date(2030, 12, 31)

# Plate suffixes are appended to --plate-prefix, e.g. "WEB 1001".
SEED_VEHICLES = [
    {"type": "1", "brand": "Honda", "model": "Click 125i", "color": "Red",
     "plate_suffix": "1001", "status": 1},
    {"type": "2", "brand": "Toyota", "model": "Vios", "color": "White",
     "plate_suffix": "2002", "status": 1},
    {"type": "3", "brand": "Toyota", "model": "Innova", "color": "Gray",
     "plate_suffix": "3003", "status": 1},
]


class Command(BaseCommand):
    help = "Seed temporary rider and customer accounts for mobile login testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--rider-mobile",
            default="9170000001",
            help="10-digit PH mobile for rider (default: 9170000001)",
        )
        parser.add_argument(
            "--customer-mobile",
            default="9170000002",
            help="10-digit PH mobile for customer (default: 9170000002)",
        )
        parser.add_argument(
            "--plate-prefix",
            default="TST",
            help="Prefix for seeded plate numbers, e.g. TST -> 'TST 1001' (default: TST)",
        )

    def handle(self, *args, **options):
        if settings.ENV not in ("development", "staging"):
            self.stderr.write(
                self.style.ERROR(
                    "Refusing to run: seed_test_accounts is for development/staging only."
                )
            )
            return

        rider_mobile = self._normalize_mobile(options["rider_mobile"])
        # Stored with the 63 prefix, like real sign-ups (login looks up 63XXXXXXXXXX).
        customer_mobile = self._normalize_mobile(options["customer_mobile"])

        if rider_mobile == customer_mobile:
            self.stderr.write(
                self.style.ERROR("Rider and customer mobile numbers must be different.")
            )
            return

        with transaction.atomic():
            rider = self._seed_rider(rider_mobile)
            customer = self._seed_customer(customer_mobile)
            self._seed_vehicles(rider, options["plate_prefix"])

            wallet_service = WalletService()
            wallet_service.create_rider_wallet(rider_id=rider.id)
            wallet_service.create_customer_wallet(customer_id=customer.id)

            # Platform wallet credited with commission on cash trips
            # (wallet_service.update_booking_wallets_for_cash looks up user_id=1).
            PinoyRideWallet.objects.get_or_create(
                user_id=1, user_type="pinoy_ride", type="pinoy-ride-wallet",
                defaults={"status": 1},
            )

        self.stdout.write(self.style.SUCCESS("\nTest accounts ready:\n"))
        self._print_account("Rider", self._app_mobile(options["rider_mobile"]), rider.id)
        self._print_account("Customer", self._app_mobile(options["customer_mobile"]), customer.id)
        self.stdout.write(
            "\nLogin in the app with the 10-digit numbers above.\n"
            "In development, OTP is returned in the API response / Metro logs.\n"
        )

    def _digits(self, mobile: str) -> str:
        return "".join(ch for ch in mobile if ch.isdigit())

    def _app_mobile(self, mobile: str) -> str:
        """10-digit format used by the mobile apps (e.g. 9170000001)."""
        digits = self._digits(mobile)
        if len(digits) == 10 and digits.startswith("9"):
            return digits
        if digits.startswith("63") and len(digits) == 12:
            return digits[2:]
        if digits.startswith("09") and len(digits) == 11:
            return digits[1:]

        raise ValueError(
            f"Invalid mobile '{mobile}'. Use 10 digits starting with 9, e.g. 9170000001."
        )

    def _normalize_mobile(self, mobile: str) -> str:
        """63-prefixed format used by rider records."""
        return CustomUtils.convert_mobile_no(self._app_mobile(mobile))

    def _seed_rider(self, mobile_no: str) -> Rider:
        rider, created = Rider.objects.update_or_create(
            mobile_no=mobile_no,
            defaults={
                "first_name": "Test",
                "middle_name": "",
                "last_name": "Rider",
                "email_address": "test.rider@pinoyride.local",
                "ekyc_request_user_id": f"dev-seed-rider-{mobile_no}",
                "application_status": 1,
                "status": 1,
                "is_success_kyc": 1,
                "is_verified": 1,
                "is_available": 1,
                "is_login": 0,
                "drivers_license_no": self._license_no(mobile_no),
                "drivers_license_no_expiration_date": SEED_LICENSE_EXPIRATION,
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} rider id={rider.id} mobile={mobile_no}"))
        self.stdout.write(
            f"  License {rider.drivers_license_no} exp {rider.drivers_license_no_expiration_date}"
        )
        return rider

    def _license_no(self, mobile_no: str) -> str:
        """LTO-style license number (Nxx-yy-zzzzzz), unique per seeded mobile."""
        digits = self._digits(mobile_no)
        return f"N01-{digits[-8:-6]}-{digits[-6:]}"

    def _seed_vehicles(self, rider: Rider, plate_prefix: str) -> None:
        prefix = normalize_plate_number(plate_prefix)
        # Active (non-soft-deleted) vehicles, keyed the same way the
        # serializer's duplicate-plate check compares them.
        existing = {}
        for vehicle in RiderVehicleDetails.objects.all():
            existing.setdefault(plate_compare_key(vehicle.v_plate_number), vehicle)

        for spec in SEED_VEHICLES:
            assert spec["type"] in ALLOWED_VEHICLE_TYPES
            plate = normalize_plate_number(f"{prefix} {spec['plate_suffix']}")
            values = {
                "v_type": spec["type"],
                "v_brand": spec["brand"],
                "v_model": spec["model"],
                "v_color": spec["color"],
                "v_plate_number": plate,
                "status": spec["status"],
            }

            vehicle = existing.get(plate_compare_key(plate))
            if vehicle and vehicle.rider_id != rider.id:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped vehicle {plate}: plate already registered to "
                        f"rider id={vehicle.rider_id}. Use a different --plate-prefix."
                    )
                )
                continue

            if vehicle:
                for field, value in values.items():
                    setattr(vehicle, field, value)
                vehicle.save()
                action = "Updated"
            else:
                vehicle = RiderVehicleDetails.objects.create(rider=rider, **values)
                existing[plate_compare_key(plate)] = vehicle
                action = "Created"

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {action} vehicle id={vehicle.id} type={vehicle.v_type} "
                    f"{vehicle.v_brand} {vehicle.v_model} {vehicle.v_color} "
                    f"plate={vehicle.v_plate_number}"
                )
            )

    def _seed_customer(self, mobile: str) -> Customer:
        # Upgrade a legacy row saved without the 63 prefix instead of creating a duplicate.
        legacy = mobile[2:] if mobile.startswith("63") else None
        if legacy and not Customer.objects.filter(mobile=mobile).exists():
            Customer.objects.filter(mobile=legacy).update(mobile=mobile)
        customer, created = Customer.objects.update_or_create(
            mobile=mobile,
            defaults={
                "fname": "Test",
                "mname": "",
                "lname": "Customer",
                "email": "test.customer@pinoyride.local",
                "customer_type": "1",
                "login_type": "mobile_number",
                "ekyc_request_user_id": f"dev-seed-customer-{mobile}",
                "status": 1,
                "is_success_kyc": 1,
                "is_verified": 1,
                "is_login": 0,
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} customer id={customer.id} mobile={mobile}")
        )
        return customer

    def _print_account(self, label: str, app_mobile: str, record_id: int) -> None:
        self.stdout.write(f"  {label}:")
        self.stdout.write(f"    App login : {app_mobile}")
        self.stdout.write(f"    Record id : {record_id}")
