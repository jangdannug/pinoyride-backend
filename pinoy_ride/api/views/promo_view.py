from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from api.services import AdminPromoService
from api.utils.app_response import AppResponse
from django.db import transaction


class PromoViewSet(viewsets.ViewSet):
    """
    Public ViewSet for Promo operations
    """
    permission_classes = [AllowAny]  # Public endpoint, API key protected via middleware

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminPromoService()

    @action(
        detail=False, methods=["post"], url_path="check"
    )
    def check_and_update_expired_promos(self, request):
        """Check and update expired promos status from active to expired"""
        try:
            with transaction.atomic():
                result = self.admin_service.check_and_update_expired_promos()

            return AppResponse.send_success(
                data=result,
                message=f"Checked {result['checked']} promos, {result['expired_count']} marked as expired",
                code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
