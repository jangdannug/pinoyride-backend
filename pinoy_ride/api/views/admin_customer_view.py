from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminCustomerService
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


