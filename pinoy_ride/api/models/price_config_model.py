from django.db import models
from .soft_delete_model import SoftDeleteModel


class PriceConfig(SoftDeleteModel):
    """
    Pricing configuration per booking type.
    Stores default pricing values that can be dynamically updated.
    """
    id = models.AutoField(primary_key=True)
    booking_type = models.CharField(max_length=50, help_text="Booking type: '1' (Motorcycle), '2' (Car 4-Seaters), '3' (Car 6-Seaters)")
    booking_type_name = models.CharField(max_length=100, help_text="Human-readable name for the booking type")

    # Distance and fare configuration
    km_basis = models.FloatField(default=7.0, help_text="Kilometer basis before excess charges apply")
    minimum_fare = models.FloatField(default=40.0, help_text="Minimum fare for this booking type")
    pesos_per_km = models.FloatField(default=10.0, help_text="Rate per kilometer within km_basis")
    pesos_per_km2 = models.FloatField(default=15.0, help_text="Rate per kilometer exceeding km_basis")

    # Fees and commissions
    booking_fee = models.FloatField(default=0.0, help_text="Additional booking fee")
    commission_percentage = models.FloatField(default=0.15, help_text="Commission percentage (e.g., 0.15 for 15%)")

    # Status and timestamps
    is_active = models.BooleanField(default=True, help_text="Whether this pricing config is active")
    status = models.IntegerField(default=1, help_text="Status: 1=active, 0=inactive")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "price_config"
        verbose_name = "Price Configuration"
        verbose_name_plural = "Price Configurations"
        indexes = [
            models.Index(fields=['booking_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['status']),
        ]
        unique_together = [['booking_type', 'deleted_at']]

    def __str__(self):
        return f"{self.booking_type_name} - Type {self.booking_type}"
