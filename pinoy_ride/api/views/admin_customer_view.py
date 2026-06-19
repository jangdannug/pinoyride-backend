from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminCustomerService,
    WalletService
)
from api.serializers import CustomerSerializer, PartialCustomerSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from api.utils.auth import get_authenticated_user


class AdminCustomerViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Admin Customer
    """

    permission_classes = [IsAuthenticated]

    # lookup_field = 'code'

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminCustomerService()
        self.wallet_service = WalletService()
        

    ## Get customer list
    @action(
        detail=False, methods=["get"], url_path="get-list"
    )
    def admin_customer_list(self, request):
        """List customer applicants with pagination and search query"""
        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            name_filter = request.query_params.get("name_filter")

            filters = {}

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            customers = self.admin_service.admin_customer_list(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=customers, message="Customers listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get customer booking history
    @action(
        detail=False, methods=["get"], url_path="get-history"
    )
    def admin_get_customer_booking_history(self, request):
        """List customer booking history with pagination and search query"""
        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            name_filter = request.query_params.get("name_filter")
            customer_id = request.query_params.get("customer_id", "")

            filters = {}

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            booking_history = self.admin_service.admin_list_customer_booking_history(
                customer_id=customer_id, page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )


            return AppResponse.send_success(
                data=booking_history, message="Customer booking history listed successfully", code=status.HTTP_200_OK
            )
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    ## Get customer by id
    @action(
        detail=False, methods=["get"], url_path="get-details"
    )
    def get_customer_detals(self, request):
        """Retrieve customer details"""

        customer_id = request.query_params.get("customer_id", "")
        if not customer_id:
            return AppResponse.send_error(message="Customer Id is required!", code=400)

        try:

            customer = self.admin_service.get_customer_by_id(customer_id)
            
            serializer = PartialCustomerSerializer(customer)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Customer fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Update customer status
    @action(
        detail=False, methods=["put"], url_path="update-status"
    )
    def update_customer_status(self, request):
        """Update customer status"""
        auth_user = get_authenticated_user(request)
        customer_id  = request.data.get("customer_id")
        customer_status  = request.data.get("status")

        if not customer_id:
            return AppResponse.send_error(message="Customer Id is required!", code=400)

        if not customer_status:
            return AppResponse.send_error(message="Customer Status is required!", code=400)

        try:
            with transaction.atomic():
                customer = self.admin_service.get_customer_by_id(customer_id=customer_id)

                update_customer_status = self.admin_service.update_customer_status(customer=customer, customer_status = customer_status, auth_user_id=auth_user.id)

                serializer = PartialCustomerSerializer(update_customer_status)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Rider status updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


    @action(
        detail=False, methods=["post"], url_path="get-wallet-history"
    )
    def get_wallet_history(self, request):
        """List customer wallet history with pagination and search query"""
        try:
            page = int(request.data.get("page", 1))
            perpage = int(request.data.get("perpage", 10))
            query = request.data.get("query", None)
            sort_by = request.data.get("sort_by")
            name_filter = request.data.get("name_filter")
            customer_id = request.data.get("customer_id", "")

            filters = {}

            if not customer_id:
                return AppResponse.send_error(message="Customer id is required", code=400)

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            wallet_history = self.wallet_service.get_wallet_history(
                user_id=customer_id, user_type='customer',  page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=wallet_history, message="Customer's wallet history listed successfully"
            )
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(
        detail=False, methods=["get"], url_path="get-wallet-summary"
    )
    def get_customer_wallet_summary(self, request):
        """Get customer wallet summary (current balance, total spent, total top-ups)"""
        try:
            customer_id = request.query_params.get("customer_id", "")

            if not customer_id:
                return AppResponse.send_error(message="Customer Id is required!", code=400)

            wallet_summary = self.admin_service.get_customer_wallet_summary(customer_id)

            return AppResponse.send_success(
                data=wallet_summary,
                message="Customer wallet summary retrieved successfully",
                code=status.HTTP_200_OK
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


