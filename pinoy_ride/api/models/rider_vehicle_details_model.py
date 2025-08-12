import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from .rider_model import Rider
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


def upload_to_or_cr(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return f"uploads/or_cr/{instance.rider.id}/{filename}"

def upload_to_motorcycle(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return f"uploads/motorcycle_img/{instance.rider.id}/{filename}"

class RiderVehicleDetails(SoftDeleteModel):
    id = models.AutoField(primary_key=True)
    rider = models.ForeignKey(Rider, related_name='rider_vehicle', on_delete=models.CASCADE, default=None, null=True, blank=True)
    v_type = models.CharField(max_length=255, null=True)
    v_brand = models.CharField(max_length=255, null=True)
    v_model = models.CharField(max_length=255, null=True)
    v_color = models.CharField(max_length=255, null=True)
    v_plate_number = models.CharField(max_length=255, null=True)
    v_or_cr_img = models.FileField(upload_to=upload_to_or_cr, null=True, blank=True)
    v_motorcyle_img = models.FileField(upload_to=upload_to_motorcycle, null=True, blank=True)
    status = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['rider_id']),
            models.Index(fields=['v_plate_number']),
            models.Index(fields=['v_type']),
            models.Index(fields=['v_brand']),
            models.Index(fields=['status']),
            models.Index(fields=['deleted_at'])
        ]
        db_table = "rider_vehicle_details"

    def __str__(self):
        return f"{self.id} - {self.rider} {self.plate_number}"
