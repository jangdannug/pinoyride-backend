from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.serializers import PriceConfigSerializer, PriceConfigDetailSerializer
from api.utils.custom_error import NotFoundError, ValidationError
from api.services import PriceConfigService


class PriceConfigViewSet(viewsets.ViewSet):
    """Price Configuration Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = PriceConfigService()

    def list(self, request):
        """Get all price configurations"""
        try:
            price_configs = self.service.get_all()
            serializer = PriceConfigSerializer(price_configs, many=True)
            return AppResponse.send_success(data=serializer.data, message="Price configurations retrieved successfully")
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    def retrieve(self, request, pk=None):
        """Get a specific price configuration by ID"""
        try:
            price_config = self.service.get_by_id(pk)
            serializer = PriceConfigDetailSerializer(price_config)
            return AppResponse.send_success(data=serializer.data, message="Price configuration retrieved successfully")
        except (NotFoundError, ValidationError) as e:
            return AppResponse.send_error(message=str(e), code=400)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    def create(self, request):
        """Create a new price configuration"""
        try:
            serializer = PriceConfigSerializer(data=request.data)
            if not serializer.is_valid():
                return AppResponse.send_error(message="Validation failed", data=serializer.errors, code=400)

            price_config = self.service.create(serializer.validated_data)
            response_serializer = PriceConfigDetailSerializer(price_config)
            return AppResponse.send_success(data=response_serializer.data, message="Price configuration created successfully")
        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    def update(self, request, pk=None):
        """Update an existing price configuration"""
        try:
            serializer = PriceConfigSerializer(data=request.data, partial=True)
            if not serializer.is_valid():
                return AppResponse.send_error(message="Validation failed", data=serializer.errors, code=400)

            price_config = self.service.update(pk, serializer.validated_data)
            response_serializer = PriceConfigDetailSerializer(price_config)
            return AppResponse.send_success(data=response_serializer.data, message="Price configuration updated successfully")
        except (NotFoundError, ValidationError) as e:
            return AppResponse.send_error(message=str(e), code=400)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    def destroy(self, request, pk=None):
        """Delete (soft delete) a price configuration"""
        try:
            self.service.delete(pk)
            return AppResponse.send_success(message="Price configuration deleted successfully")
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    @action(detail=False, methods=['get'], url_path='booking-type/(?P<booking_type>[^/]+)')
    def get_by_booking_type(self, request, booking_type=None):
        """Get price configuration by booking type"""
        try:
            price_config = self.service.get_by_booking_type(booking_type)
            serializer = PriceConfigDetailSerializer(price_config)
            return AppResponse.send_success(data=serializer.data, message=f"Price config for booking type '{booking_type}' retrieved successfully")
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Restore a soft deleted price configuration"""
        try:
            price_config = self.service.restore(pk)
            serializer = PriceConfigDetailSerializer(price_config)
            return AppResponse.send_success(data=serializer.data, message="Price configuration restored successfully")
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)
