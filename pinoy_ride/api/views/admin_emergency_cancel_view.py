"""US-7.3 admin APIs: list rider emergency cancellations and approve/reject them."""
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated

from api.services.advance_booking_service import AdvanceBookingService
from api.utils.app_response import AppResponse
from api.utils.custom_error import NotFoundError, ValidationError
from rest_framework.decorators import action


class AdminEmergencyCancelViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = AdvanceBookingService()

    def list(self, request):
        try:
            data = self.service.list_emergency_requests(
                status=request.query_params.get("status") or "pending",
                page=request.query_params.get("page", 1),
                perpage=request.query_params.get("perpage", 10))
            return AppResponse.send_success(data=data, message="Emergency cancellations listed successfully")
        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        try:
            data = self.service.decide_emergency(
                pk, request.data.get("decision"), reason=request.data.get("reason"), admin_user=request.user)
            return AppResponse.send_success(data=data, message="Emergency cancellation decided")
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR)
