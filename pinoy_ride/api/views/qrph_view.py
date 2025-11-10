from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from django.db import transaction
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from api.utils.app_logger import app_logger
from api.serializers import QRPhCallbackSerializer
from api.services import (
    QrphApiService,
    CustomerService,
    RiderService
)
import uuid

class QrphViewSet(viewsets.ViewSet):
    """QRPH Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs),
        self.qrph_service = QrphApiService()
        self.customer_service = CustomerService()
        self.rider_service = RiderService()

    @action(detail=False, methods=['post'], url_path='authenticate')
    def authenticate(self, request):
        """Authenticate View"""

        try:            
            
            response = self.qrph_service.authenticate()

            return AppResponse.send_success(data=response, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
             
            return AppResponse.send_error(message=str(e), code=500)    
        
        
        
    @action(detail=False, methods=['post'], url_path='request-to-pay')
    def request_to_pay(self, request):
        """Request to Pay"""
        
        try:            
            data = request.data
            app_logger(1, "Request to Pay Request", data)

            # Validate required fields
            required_fields = ['amount', 'total_amount', 'user_id', 'user_type']
            for field in required_fields:
                if field not in data:
                    return AppResponse.send_error(message=str(f"Missing required field: {field}"), code=400)
            
            user_id = data.get('user_id')
            user_type = data.get('user_type')

            if user_type == 'customer':
                self.customer_service.get_customer_by_id(customer_id=user_id)    
            elif user_type == 'rider':
                self.rider_service.get_rider_by_id(rider_id=user_id)
            else:
                return AppResponse.send_error(message="Invalid user type", code=400)
            
            with transaction.atomic():
                result = self.qrph_service.request_to_pay(
                    user_id=user_id,
                    user_type=user_type,
                    amount=float(data.get('amount', 0.0)),
                    total_amount=float(data.get('total_amount', 0.0)),
                    reference_id=str(uuid.uuid4()),
                    client_title=data.get('client_title', "Pinoy Ride"),
                    client_logo=data.get('client_logo', "https://pinoyride.com/assets/img/pinoyride-logo.png"),
                    exp_in_mins=data.get('expInMins', 30),
                    discount=float(data.get('discount', 0.0)),
                    tax=float(data.get('tax', 0.0)),
                    trxn_fee=float(data.get('trxn_fee', 0.0)),
                    order_details=data.get('order_details', [])
            )

            return AppResponse.send_success(
                data={
                    "paymentUrl": result['response'].get('url'),
                    "referenceId": result['response'].get('referenceId'),
                    "invoiceId": result['response'].get('invoiceId'),
                    "partnerReferenceId": result['transaction'].partner_reference_id,
                    "expiresAt": result['transaction'].expires_at.isoformat()
                },
                message="Payment request created successfully"
            )   


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    @action(detail=False, methods=['post'], url_path='callback')
    def qrph_callback(self, request):
        """Callback"""
        
        try:            
            callback_request = request.data
            app_logger(1, "QRPh Callback Request", callback_request)

            callback_data = request.data.get('data', {})
            callback_hash = request.data.get('hash', '')
            
            # # Validate callback structure
            serializer = QRPhCallbackSerializer(data=callback_data)
            if not serializer.is_valid():
                    return AppResponse.send_error(message=serializer.errors, code=400)
            
            # Process callback
            with transaction.atomic():
                transaction_resp = self.qrph_service.process_callback(
                    callback_data=callback_data,
                    callback_hash=callback_hash
                )
        
            
            return AppResponse.send_success(
                data={
                    "referenceId": transaction_resp.reference_id,
                    "status": transaction_resp.status,
                    "processed": True
                },
                message="Callback processed successfully"
            )
            # return AppResponse.send_success(data=callback_request, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   


    @action(detail=False, methods=['post'], url_path='check_status')
    def qrph_check_status(self, request):
        """QRPH Check Status"""
        
        try:            
            reference_id = request.data.get('reference_id', '')
            
            if not reference_id:
                return AppResponse.send_error(message=str("Reference ID is required"), code=400)
            
            status = 'not-found'

            # Check status
            transaction = self.qrph_service.check_status(reference_id=reference_id)
            if transaction:
                status = transaction.status
        
            return AppResponse.send_success(
                data={
                    "referenceId": reference_id,
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

