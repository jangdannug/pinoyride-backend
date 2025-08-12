from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test

class TestViewSet(viewsets.ViewSet):
    """Test Controller"""

    queryset = Test.objects.all()

    @extend_schema(
        methods=['POST'],  # Specify the HTTP methods this endpoint responds to
        description="Return sample response",  # Brief description of the endpoint
        tags=['Test'],  # Optional tag to categorize this endpoint
    )
    @action(detail=False, methods=['post'], url_path='test')
    def default(self, request):
        """Return sample response"""
        return AppResponse.send_success(data=None, message="Django restful template 123")
