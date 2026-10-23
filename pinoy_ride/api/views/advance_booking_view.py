"""Book Later / Arrived at Pickup / Try Again / ETA endpoints, mixed into BookingViewSet."""
from functools import wraps

from rest_framework.decorators import action

from api.models.customer_model import Customer
from api.models.rider_model import Rider
from api.serializers import BookingSerializer
from api.services.advance_booking_service import AdvanceBookingService, ConflictError
from api.utils.app_response import AppResponse
from api.utils.custom_error import NotFoundError, ValidationError


def _handle(fn):
    @wraps(fn)
    def wrapper(self, request, *args, **kwargs):
        try:
            return fn(self, request, *args, **kwargs)
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except ConflictError as e:
            return AppResponse.send_error(message=str(e), code=409)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)
    return wrapper


def _truthy(v):
    return str(v).lower() in ("1", "true", "yes")


def _req(request, name):
    v = request.data.get(name, "")
    if v in ("", None):
        raise ValidationError(f"{name.replace('_', ' ').capitalize()} is required")
    return v


def _rider(request):
    rider = Rider.objects.filter(id=_req(request, "rider_id")).first()
    if rider is None:
        raise NotFoundError("Rider not found")
    return rider


def _customer_id(request):
    cid = _req(request, "customer_id")
    if not Customer.objects.filter(id=cid).exists():
        raise NotFoundError("Customer not found")
    return cid


class AdvanceBookingMixin:
    advance_service = AdvanceBookingService()

    # Passenger -------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="get_upcoming")
    @_handle
    def get_upcoming(self, request):
        data = self.advance_service.get_upcoming(_customer_id(request), page=int(request.data.get("page", 1) or 1))
        return AppResponse.send_success(data=data, message="Upcoming bookings fetched successfully")

    @action(detail=False, methods=["post"], url_path="cancel_advance")
    @_handle
    def cancel_advance(self, request):
        data = self.advance_service.cancel_by_customer(
            _customer_id(request), _req(request, "booking_id"),
            reason=request.data.get("reason"), preview=_truthy(request.data.get("preview")))
        return AppResponse.send_success(data=data, message="Preview" if data.get("status") != 4 else "Booking cancelled")

    @action(detail=False, methods=["post"], url_path="retry")
    @_handle
    def retry_booking(self, request):
        booking = self.advance_service.retry(_customer_id(request), _req(request, "booking_id"))
        return AppResponse.send_success(data=BookingSerializer(booking).data, message="Searching for riders again")

    @action(detail=False, methods=["post"], url_path="get_eta")
    @_handle
    def get_eta(self, request):
        booking_id = _req(request, "booking_id")
        cid, rid = request.data.get("customer_id"), request.data.get("rider_id")
        if not cid and not rid:
            raise ValidationError("Customer id or rider id is required")
        return AppResponse.send_success(
            data=self.advance_service.get_eta(booking_id, customer_id=cid, rider_id=rid), message="ETA fetched")

    # Rider -----------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="get_advance_pending")
    @_handle
    def get_advance_pending(self, request):
        data = self.advance_service.advance_pending(
            _rider(request), request.data.get("current_lat"), request.data.get("current_long"),
            page=int(request.data.get("page", 1) or 1))
        return AppResponse.send_success(data=data, message="Advance bookings fetched successfully")

    @action(detail=False, methods=["post"], url_path="accept_advance")
    @_handle
    def accept_advance(self, request):
        booking = self.advance_service.accept(_rider(request), _req(request, "booking_id"))
        return AppResponse.send_success(data=BookingSerializer(booking).data, message="Advance booking accepted")

    @action(detail=False, methods=["post"], url_path="get_advance_details")
    @_handle
    def get_advance_details(self, request):
        data = self.advance_service.details(_rider(request), _req(request, "booking_id"))
        return AppResponse.send_success(data=data, message="Advance booking details fetched successfully")

    @action(detail=False, methods=["post"], url_path="start_advance")
    @_handle
    def start_advance(self, request):
        booking = self.advance_service.start(_rider(request), _req(request, "booking_id"))
        return AppResponse.send_success(data=BookingSerializer(booking).data, message="Heading to pickup")

    @action(detail=False, methods=["post"], url_path="arrived_at_pickup")
    @_handle
    def arrived_at_pickup(self, request):
        booking = self.advance_service.arrived(
            _rider(request), _req(request, "booking_id"), _req(request, "current_lat"), _req(request, "current_long"))
        return AppResponse.send_success(data=BookingSerializer(booking).data, message="Passenger notified")

    @action(detail=False, methods=["post"], url_path="cancel_advance_rider")
    @_handle
    def cancel_advance_rider(self, request):
        data = self.advance_service.cancel_by_rider(
            _rider(request), _req(request, "booking_id"),
            reason=request.data.get("reason"), preview=_truthy(request.data.get("preview")))
        return AppResponse.send_success(data=data, message="Booking released")

    @action(detail=False, methods=["post"], url_path="cancel_emergency_rider")
    @_handle
    def cancel_emergency_rider(self, request):
        data = self.advance_service.cancel_emergency_by_rider(
            _rider(request), _req(request, "booking_id"), reason=request.data.get("reason"))
        return AppResponse.send_success(data=data, message="Emergency cancellation sent for admin review")
