from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
from django.conf import settings
from geopy.distance import geodesic

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


    @action(detail=False, methods=['post'], url_path='compute_distance')
    def compute_distance(self, request):
        """Return sample response"""

        origin_lat = request.data.get("origin_lat", "")
        origin_long = request.data.get("origin_long", "")
        destination_lat = request.data.get("destination_lat", "")
        destination_long= request.data.get("destination_long", "")

         # origin
        origin = (origin_lat, origin_long)   # (lat, lng)
        # destination
        destination = (destination_lat, destination_long)

        # compute distance in kilometers
        distance_km = geodesic(origin, destination).kilometers
        response = {
            "distance_km_round" : round(distance_km, 2)
        }

        return AppResponse.send_success(data=response, message="Success")


    @action(detail=False, methods=['post'], url_path='env_check')
    def env_check(self, request):
        """Return sample response"""
        return AppResponse.send_success(
                data={
                    "status": "success",
                    "message": "Service is live! ",
                    "env: CUSTOM_API_KEY" : settings.CUSTOM_API_KEY,
                    "env: ENV" : settings.ENV,
                    "env: SECRET_KEY" : settings.SECRET_KEY,
                    "env: API_KEY" : settings.API_KEY
                    
                },
                code=200,
            )
