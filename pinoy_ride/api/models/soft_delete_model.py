from django.db import models
from django.utils.timezone import now


class SoftDeleteManager(models.Manager):
    """Custom manager to filter out soft-deleted records"""
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        return super().get_queryset()

class SoftDeleteModel(models.Model):
    """Abstract base model for soft delete functionality"""
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()  
    all_objects = models.Manager()  

    def delete(self, using=None, keep_parents=False):
        """Override delete method to perform a soft delete"""
        self.deleted_at = now()
        self.save(update_fields=["deleted_at"])

    def delete_booking(self, using=None, keep_parents=False):
        """Special method for delete booking"""
        self.deleted_at = now()
        self.status = 9
        self.save(update_fields=["deleted_at", "status"])

    def restore(self):
        """Restore a soft-deleted record"""
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    class Meta:
        abstract = True  
