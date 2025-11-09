import string
from django.db import models
from django.utils.crypto import get_random_string
from .soft_delete_model import SoftDeleteModel
from django.db import transaction
from django.db.models import Max
from uuid import uuid4

from storages.backends.s3boto3 import S3Boto3Storage


class TopPhEkycDetails(SoftDeleteModel):

    id = models.AutoField(primary_key=True)
    generate_request_user_id = models.CharField(max_length=150, unique=True, db_index=True, null=True)
    kyc_id = models.CharField(max_length=150, db_index=True)
    first_name = models.CharField(max_length=150, null=True)
    middle_name = models.CharField(max_length=150, null=True)
    last_name = models.CharField(max_length=150, null=True)
    email_address = models.CharField(max_length=150, null=True)
    mobile_no = models.CharField(max_length=150, null=True)
    pretty_mobile_no = models.CharField(max_length=150, null=True)
    date_of_birth = models.CharField(max_length=150, null=True)
    place_of_birth = models.CharField(max_length=150, null=True)
    nationality = models.CharField(max_length=150, null=True)
    gender = models.CharField(max_length=150, null=True)
    current_country = models.CharField(max_length=150, null=True)
    current_address = models.CharField(max_length=250, null=True)
    permanent_country = models.CharField(max_length=150, null=True)
    permanent_address = models.CharField(max_length=150, null=True)
    nature_of_work = models.CharField(max_length=150, null=True)
    source_of_fund = models.CharField(max_length=150, null=True)
    id_type = models.CharField(max_length=150, null=True)
    id_number = models.CharField(max_length=150, null=True)
    id_front = models.TextField(blank=True, null=True)
    id_back = models.TextField(blank=True, null=True)
    selfie = models.TextField(blank=True, null=True)
    status = models.IntegerField(default=0)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['kyc_id']),
            models.Index(fields=['mobile_no']),
            models.Index(fields=['pretty_mobile_no']),
            models.Index(fields=['generate_request_user_id']),
        ]
        db_table = "top_ph_ekyc_details"
        

    def __str__(self):
        return f"{self.user_id} - {self.zkyc_id}"
