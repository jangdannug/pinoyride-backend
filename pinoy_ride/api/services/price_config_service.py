from django.db import transaction
from api.repositories import PriceConfigRepository
from api.utils.custom_error import NotFoundError, ValidationError


class PriceConfigService:
    """Service for PriceConfig business logic"""

    def __init__(self):
        self.repository = PriceConfigRepository()

    def get_all(self):
        """Get all active price configs"""
        return self.repository.get_all()

    def get_by_id(self, price_config_id):
        """Get price config by ID"""
        price_config = self.repository.get_by_id(price_config_id)
        if not price_config:
            raise NotFoundError("Price config not found")
        return price_config

    def get_by_booking_type(self, booking_type):
        """Get price config by booking type"""
        price_config = self.repository.get_by_booking_type(booking_type)
        if not price_config:
            raise NotFoundError(f"Price config for booking type '{booking_type}' not found")
        return price_config

    def get_all_active(self):
        """Get all active price configs"""
        return self.repository.get_all_active()

    @transaction.atomic
    def create(self, data):
        """Create a new price config"""
        # Check if booking type already exists
        existing = self.repository.get_by_booking_type(data.get('booking_type'))
        if existing:
            raise ValidationError(f"Price config for booking type '{data.get('booking_type')}' already exists")

        return self.repository.create(**data)

    @transaction.atomic
    def update(self, price_config_id, data):
        """Update an existing price config"""
        price_config = self.get_by_id(price_config_id)

        # If booking_type is being updated, check for conflicts
        if 'booking_type' in data and data['booking_type'] != price_config.booking_type:
            existing = self.repository.get_by_booking_type(data['booking_type'])
            if existing and existing.id != price_config_id:
                raise ValidationError(f"Price config for booking type '{data['booking_type']}' already exists")

        return self.repository.update(price_config, **data)

    @transaction.atomic
    def delete(self, price_config_id):
        """Soft delete a price config"""
        price_config = self.get_by_id(price_config_id)
        self.repository.delete(price_config)

    @transaction.atomic
    def restore(self, price_config_id):
        """Restore a soft deleted price config"""
        price_config = self.repository.restore(price_config_id)
        if not price_config:
            raise NotFoundError("Price config not found or already active")
        return price_config

    def get_pricing_for_booking(self, booking_type):
        """
        Get pricing configuration for a specific booking type.
        Returns a dictionary with all pricing values.
        Raises NotFoundError if config doesn't exist.
        """
        config = self.get_by_booking_type(booking_type)
        return {
            'km_basis': config.km_basis,
            'minimum_fare': config.minimum_fare,
            'pesos_per_km': config.pesos_per_km,
            'pesos_per_km2': config.pesos_per_km2,
            'booking_fee': config.booking_fee,
            'commission_percentage': config.commission_percentage
        }
