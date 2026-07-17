from api.models import PriceConfig
from django.core.exceptions import ObjectDoesNotExist


class PriceConfigRepository:
    """Repository for PriceConfig data access operations"""

    def get_all(self):
        """Get all price configs"""
        return PriceConfig.objects.filter(is_active=True)

    def get_by_id(self, price_config_id):
        """Get price config by ID"""
        try:
            return PriceConfig.objects.get(id=price_config_id, is_active=True)
        except ObjectDoesNotExist:
            return None

    def get_by_booking_type(self, booking_type):
        """Get price config by booking type"""
        try:
            return PriceConfig.objects.filter(booking_type=booking_type, is_active=True).first()
        except ObjectDoesNotExist:
            return None

    def get_all_active(self):
        """Get all active price configs"""
        return PriceConfig.objects.filter(is_active=True, status=1)

    def create(self, **kwargs):
        """Create a new price config"""
        return PriceConfig.objects.create(**kwargs)

    def update(self, price_config, **kwargs):
        """Update an existing price config"""
        for key, value in kwargs.items():
            setattr(price_config, key, value)
        price_config.save()
        return price_config

    def delete(self, price_config):
        """Soft delete a price config"""
        price_config.delete()

    def restore(self, price_config_id):
        """Restore a soft deleted price config"""
        price_config = PriceConfig.all_objects.filter(id=price_config_id).first()
        if price_config:
            price_config.deleted_at = None
            price_config.is_active = True
            price_config.status = 1
            price_config.save()
        return price_config
