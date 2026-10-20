"""
Ensure price_config rows exist for motorcycle (1), car 4-seater (2), and car 6-seater (3).

Rates are illustrative — tune minimum_fare / pesos_per_km / pesos_per_km2 to match product.

  python manage.py seed_price_configs
"""
from django.core.management.base import BaseCommand

from api.models.price_config_model import PriceConfig

DEFAULTS = [
    {
        "booking_type": "1",
        "booking_type_name": "Motorcycle",
        "km_basis": 7.0,
        "minimum_fare": 40.0,
        "pesos_per_km": 10.0,
        "pesos_per_km2": 15.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
    {
        "booking_type": "2",
        "booking_type_name": "Car (4 Seaters)",
        "km_basis": 7.0,
        "minimum_fare": 120.0,
        "pesos_per_km": 25.0,
        "pesos_per_km2": 35.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
    {
        "booking_type": "3",
        "booking_type_name": "Car (6 Seaters)",
        "km_basis": 7.0,
        "minimum_fare": 140.0,
        "pesos_per_km": 28.0,
        "pesos_per_km2": 40.0,
        "booking_fee": 0.0,
        "commission_percentage": 0.15,
    },
]


class Command(BaseCommand):
    help = "Create or update price_config per vehicle type (1/2/3)."

    def handle(self, *args, **options):
        for row in DEFAULTS:
            obj = PriceConfig.objects.filter(
                booking_type=row["booking_type"],
                deleted_at__isnull=True,
            ).first()
            created = obj is None
            if created:
                obj = PriceConfig()
            for key, value in row.items():
                setattr(obj, key, value)
            obj.is_active = True
            obj.status = 1
            obj.save()
            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} type {row['booking_type']} ({row['booking_type_name']}): "
                    f"min ₱{row['minimum_fare']}, ₱{row['pesos_per_km']}/km, "
                    f"₱{row['pesos_per_km2']}/km exceed"
                )
            )
