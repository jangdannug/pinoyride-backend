from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from django.db import transaction
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from api.utils.app_logger import app_logger
from api.serializers import QRPhCallbackSerializer
from api.services import (
    CashOutApiService,
    CustomerService,
    RiderService
)
import uuid
from api.models.top_ph_ekyc_callback_logs_model import TopPhEkycCallbackLogsModel
import json

class CashOutViewSet(viewsets.ViewSet):
    """Cash Out Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs),
        self.cash_out_service = CashOutApiService()
        self.customer_service = CustomerService()
        self.rider_service = RiderService()

    @action(detail=False, methods=['post'], url_path='authenticate')
    def authenticate(self, request):
        """Authenticate View"""

        try:            
            
            response = self.cash_out_service.authenticate()

            return AppResponse.send_success(data=response, message="Success")


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
             
            return AppResponse.send_error(message=str(e), code=500)    
        
    

    @action(detail=False, methods=['post'], url_path='get-banks')
    def cash_out_get_banks(self, request):
        """CashOut Get Banks"""
        
        try:            
            banks = self.cash_out_service.get_banks()
        
            return AppResponse.send_success(
                data=banks,
                message="Success"
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   

        
    @action(detail=False, methods=['post'], url_path='cash-out')
    def cash_out(self, request):
        """Cash-out"""
        
        try:            
            data = request.data
            app_logger(1, "Cashout Request", data)

            # Validate required fields
            required_fields = ['destination_acct_name', 'destination_acct_no', 'destination_bank_code', 'amount', 'user_id', 'user_type']
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
                result = self.cash_out_service.cash_out(
                    user_id=user_id,
                    user_type=user_type,
                    amount=float(data.get('amount', 0.0)),
                    destination_acct_name=data.get('destination_acct_name', ""),
                    destination_acct_no=data.get('destination_acct_no', ""),
                    destination_bank_code=data.get('destination_bank_code', "")
            )

            return AppResponse.send_success(
                data={          
                    "msg_status": result['msg_status'],
                    "message": result['response'].get('message'),
                    "ref_no": result['response'].get('txnRefNo'),
                    "invoice_no": result['response'].get('invNo'),
                    "txnAmt": result['response'].get('txnAmt'),
                    "transactionDate": result['response'].get('transactionDate'),
                },
                message="Success"
            )   
        


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)




    @action(detail=False, methods=['post'], url_path='check_status')
    def cashout_check_status(self, request):
        """Cashout Check Status"""
        
        try:            
            reference_id = request.data.get('reference_id', '')
            
            if not reference_id:
                return AppResponse.send_error(message=str("Reference ID is required"), code=400)
            
            # Check status
            status_response = self.cash_out_service.cashout_check_status(reference_id=reference_id)
        
            return AppResponse.send_success(
                data=status_response,
                message="Success"
            )


        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)   

