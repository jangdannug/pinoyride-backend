from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from api.models import Test
from django.conf import settings
from geopy.distance import geodesic
from api.utils.top_ph_ekyc_security import TopPhEkycSecurityUtil
import base64
import hashlib
import json

class TestViewSet(viewsets.ViewSet):
    """Test Controller"""

    def __init__(self, *args, **kwargs):
        self.ekyc_config = settings.TOP_PH_EKYC_CONFIG
        self.security = TopPhEkycSecurityUtil()

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
    

    @action(detail=False, methods=['post'], url_path='generate_ekyc_callback_payload')
    def generate_ekyc_callback_payload(self, request):
        """Return sample response"""

        callback_raw_data = request.data.get("raw_data", "")
        salt = self.ekyc_config['CLIENT_SECRET']

        ## Create json string
        data_json = json.dumps(callback_raw_data, separators=(',', ':'))
        
        # Encode data
        encoded_data = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')

        # Generate hash
        combined = str(data_json) + str(salt)
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        computed_hash = base64.b64encode(hash_obj.digest()).decode('utf-8')
        

        return AppResponse.send_success(
                data={
                    "raw_data" : callback_raw_data,
                    "computed_hash" : computed_hash,
                    "encoded_data" : encoded_data
                },
                code=200,
            )
