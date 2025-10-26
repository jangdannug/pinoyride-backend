from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from django.db import transaction
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from api.utils.app_logger import app_logger
from api.serializers import QRPhCallbackSerializer
from api.services import (
    EkycApiService
)
import uuid

class EkycViewSet(viewsets.ViewSet):
    """EKYC Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs),
        self.ekyc_service = EkycApiService()

    @action(detail=False, methods=['post'], url_path='authenticate')
    def authenticate(self, request):
        """Authenticate View"""

        try:            
            response = self.ekyc_service.authenticate()

            return AppResponse.send_success(data=response, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
             
            return AppResponse.send_error(message=str(e), code=500)    
    


    @action(detail=False, methods=['post'], url_path='get-ekyc-url')
    def get_ekyc_url(self, request):
        """Get EKYC URL"""
        
        try:            
            data = request.data
            app_logger(1, "Generate eKYC URL Request", data)

            # Validate required fields
            if 'user_id' not in data:
                raise ValidationError("Missing required field: user_id")
                
            response = self.ekyc_service.generate_ekyc_url(
                user_id=data['user_id'],
                success_url=data.get('success_url', 'https://pinoyride.com/success.html'),
                failed_url=data.get('failed_url', 'https://pinoyride.com/failed.html'),
                expired_url=data.get('expired_url', 'https://pinoyride.com/expire.html')
            )
            
            return AppResponse.send_success(data=response, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)
        
    
    @action(detail=False, methods=['post'], url_path='callback')
    def ekyc_callback(self, request):
        """Callback"""
        
        try:
            callback_request = request.data
            app_logger(1, "EKYC Callback Request", callback_request)            

            callback_data = request.data.get('data', {})
            callback_hash = request.data.get('hash', '')
            
            # # Validate callback structure
            # serializer = QRPhCallbackSerializer(data=callback_data)
            # serializer.is_valid(raise_exception=True)
            
            # # Process callback
            # with transaction.atomic():
            #     transaction = self.qrph_service.process_callback(
            #         callback_data=callback_data,
            #         callback_hash=callback_hash
            #     )
        
            
            # return AppResponse.send_success(
            #     data={
            #         "referenceId": transaction.reference_id,
            #         "status": transaction.status,
            #         "processed": True
            #     },
            #     message="Callback processed successfully"
            # )
            return AppResponse.send_success(data=callback_request, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   