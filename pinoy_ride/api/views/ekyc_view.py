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
from api.models.top_ph_ekyc_callback_logs_model import TopPhEkycCallbackLogsModel
import uuid
import json

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
            if 'user_type' not in data:
                raise ValidationError("Missing required field: user_type")
            
            with transaction.atomic():
                response = self.ekyc_service.generate_ekyc_url(
                    user_id=data['user_id'],
                    user_type=data['user_type'],
                    success_url=data.get('success_url', 'https://pinoy-ride.vercel.app/ekyc-success'),
                    failed_url=data.get('failed_url', 'https://pinoy-ride.vercel.app/ekyc-failed'),
                    expired_url=data.get('expired_url', 'https://pinoy-ride.vercel.app/ekyc-expired')
                )
            
            return AppResponse.send_success(data={
                    "request_user_id": response.get('result', {}).get('userId', ''),
                    "zkyc_id": response.get('result', {}).get('zkycId', ''),
                    "zkyc_url": response.get('result', {}).get('zkycUrl', ''),
                    "trx_date": response.get('result', {}).get('trxDate', ''),
                }, message="Success")


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

            encoded_data = request.data.get('data', {})
            callback_hash = request.data.get('hash', '')
            
            request_payload = {
                "method": request.method,
                "path": request.path,
                "headers": dict(request.headers),
                "query_params": request.query_params.dict(),
                "body": request.data,
            }
            TopPhEkycCallbackLogsModel.objects.create(
                request_data=json.dumps(request_payload)
            )
        
            if not encoded_data or not callback_hash:
                raise ValidationError("Missing data or hash in callback")
            
            # Process and verify callback
            with transaction.atomic():
                callback_data = self.ekyc_service.process_callback(
                    encoded_data=encoded_data,
                    callback_hash=callback_hash
                )
            
            return AppResponse.send_success(data=callback_data, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   
        

    @action(detail=False, methods=['post'], url_path='check_status')
    def ekyc_check_status(self, request):
        """EKYC check status"""
        
        try:            
            request_user_id = request.data.get('request_user_id', '')
            
            if not request_user_id:
                return AppResponse.send_error(message=str("Request User ID is required"), code=400)
            
            status = 'not-found'

            # Check status
            ekyc_resp = self.ekyc_service.check_status(request_user_id=request_user_id)
            if ekyc_resp:
                status = ekyc_resp.status
        
            return AppResponse.send_success(
                data={
                    "request_user_id": request_user_id,
                    "status": status,
                },
                message="Success"
            )


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   


    @action(detail=False, methods=['post'], url_path='get-user-details')
    def get_user_details(self, request):
        """Get User Details"""
        
        try:            
            data = request.data
            app_logger(1, "Get User Details", data)

            # Validate required fields
            ref_id = request.data.get('ref_id', '')
            
            if not ref_id:
                return AppResponse.send_error(message=str("Ref ID is required"), code=400)
            
            with transaction.atomic():    
                response = self.ekyc_service.get_topph_user_details(
                    ref_id=ref_id
                )
            
            return AppResponse.send_success(data=response, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)