from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminPromoService
)
from api.serializers import PromoSerializer, PartialPromoSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from api.utils.auth import get_authenticated_user


class AdminPromoViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Admin Promo
    """

    permission_classes = [IsAuthenticated]

    # lookup_field = 'code'

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminPromoService()


    ## Add new promo
    @action(
        detail=False, methods=["post"], url_path="create"
    )
    def add_promo(self, request):
        """
        Add new promo
        """

        try:
            auth_user = get_authenticated_user(request)

            promo_serializer = PromoSerializer(data=request.data)
            if not promo_serializer.is_valid():
                return AppResponse.send_error(message=promo_serializer.errors, code=400)
            
            with transaction.atomic():
                promo = self.admin_service.create_promo(promo = request.data, auth_user_id = auth_user.id)
                serializer = PromoSerializer(promo)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Promo added successfully", code=201
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    ## Get promo by id
    @action(
        detail=False, methods=["get"], url_path="get"
    )
    def get_promo_by_id(self, request):
        """Retrieve promo"""

        promo_id = request.query_params.get("promo_id", "")
        if not promo_id:
            return AppResponse.send_error(message="Promo Id is required!", code=400)

        try:

            promo = self.admin_service.get_promo_by_id(promo_id)
            
            serializer = PartialPromoSerializer(promo)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Promo fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Update promo
    @action(
        detail=False, methods=["put"], url_path="update"
    )
    def update_promo(self, request):
        """Update promo"""
        promo_id  = request.data.get("promo_id")

        if not promo_id:
            return AppResponse.send_error(message="Promo Id is required!", code=400)
    
        try:
            with transaction.atomic():
                promo = self.admin_service.get_promo_by_id(promo_id=promo_id)

                promo_serializer = PromoSerializer(instance=promo, data=request.data)
                if not promo_serializer.is_valid():
                    return AppResponse.send_error(message=promo_serializer.errors, code=400)

                update_promo = self.admin_service.update_promo(promo=promo, update_data = request.data)

                serializer = PromoSerializer(update_promo)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Promo updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




     ## Update promo status
    @action(
        detail=False, methods=["put"], url_path="update_status"
    )
    def update_promo_status(self, request):
        """Update promo status"""
        promo_id  = request.data.get("promo_id")
        promo_status  = request.data.get("promo_status")

        if not promo_id:
            return AppResponse.send_error(message="Promo Id is required!", code=400)

        if not promo_status:
            return AppResponse.send_error(message="Promo Status is required!", code=400)
    
        try:
            with transaction.atomic():
                promo = self.admin_service.get_promo_by_id(promo_id=promo_id)

                update_promo_status = self.admin_service.update_promo_status(promo=promo, promo_status = promo_status)

                serializer = PromoSerializer(update_promo_status)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Promo updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get promo list
    @action(
        detail=False, methods=["get"], url_path="list"
    )
    def admin_list_promos(self, request):
        """List promos with pagination and search query"""
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

            promos = self.admin_service.admin_list_promos(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=promos, message="Promos listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

