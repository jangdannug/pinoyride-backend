from django.db import transaction
from api.models import Customer
import datetime
from api.models import (
    OtpApiRequest,
)
from django.db.models import Func, F, Value, CharField
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.db.models import Q, Max, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Concat
from django.utils.timezone import now
from datetime import timedelta
from api.serializers import (
    PromoSerializer, PartialPromoSerializer
)

class OtpApiRequestRepository:
   
    @staticmethod
    def create(mobile_no, payload, response_data):
        """Creates otp API request data."""

        return OtpApiRequest.objects.create(
            mobile_no=mobile_no,
            payload_data=payload,
            response_data=response_data
        )
    