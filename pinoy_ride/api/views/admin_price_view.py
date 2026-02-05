from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminPriceService
)
from api.serializers import PriceSerializer, PartialPriceSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from api.utils.auth import get_authenticated_user


class AdminPriceViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Admin Price
    """

    permission_classes = [IsAuthenticated]

    # lookup_field = 'code'

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminPriceService()


    ## Add new price
    @action(
        detail=False, methods=["post"], url_path="create"
    )
    def add_price(self, request):
        """
        Add new price
        """

        try:
            auth_user = get_authenticated_user(request)

            price_serializer = PriceSerializer(data=request.data)
            if not price_serializer.is_valid():
                return AppResponse.send_error(message=price_serializer.errors, code=400)
            
            with transaction.atomic():
                price = self.admin_service.create_price(price = request.data, auth_user_id = auth_user.id)
                serializer = PriceSerializer(price)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Price added successfully", code=201
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    ## Import prices
    @action(
        detail=False, methods=["post"], url_path="import"
    )
    def import_prices(self, request):
        """
        Import prices
        """

        try:
            auth_user = get_authenticated_user(request)

            import_prices = json.loads(request.data.get("import_data", "[]"))

            price_serializer = PriceSerializer(data=import_prices, many=True)
            if not price_serializer.is_valid():
                return AppResponse.send_error(message=price_serializer.errors, code=400)
            
            for price in import_prices:
                with transaction.atomic():
                    price = self.admin_service.create_price(price = price, auth_user_id = auth_user.id)
                    serializer = PriceSerializer(price)
                    response_data = serializer.data

            return AppResponse.send_success(
                data=import_prices, message="Import success", code=201
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    ## Get price by id
    @action(
        detail=False, methods=["get"], url_path="get"
    )
    def get_price_by_id(self, request):
        """Retrieve price"""

        price_id = request.query_params.get("price_id", "")
        if not price_id:
            return AppResponse.send_error(message="Price Id is required!", code=400)

        try:

            promo = self.admin_service.get_price_by_id(price_id)
            
            serializer = PartialPriceSerializer(promo)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Price fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Update price
    @action(
        detail=False, methods=["put"], url_path="update"
    )
    def update_price(self, request):
        """Update price"""
        price_id  = request.data.get("price_id")

        if not price_id:
            return AppResponse.send_error(message="Price Id is required!", code=400)
    
        try:
            with transaction.atomic():
                price = self.admin_service.get_price_by_id(price_id=price_id)

                price_serializer = PriceSerializer(instance=price, data=request.data)
                if not price_serializer.is_valid():
                    return AppResponse.send_error(message=price_serializer.errors, code=400)

                update_price = self.admin_service.update_price(price=price, update_data = request.data)

                serializer = PriceSerializer(update_price)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Price updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




     ## Update price status
    @action(
        detail=False, methods=["put"], url_path="update_status"
    )
    def update_price_status(self, request):
        """Update price status"""
        price_id  = request.data.get("price_id")
        price_status  = request.data.get("price_status")

        if not price_id:
            return AppResponse.send_error(message="Price Id is required!", code=400)

        if not price_status:
            return AppResponse.send_error(message="Price Status is required!", code=400)
    
        try:
            with transaction.atomic():
                price = self.admin_service.get_price_by_id(price_id=price_id)

                update_price_status = self.admin_service.update_price_status(price=price, price_status = price_status)

                serializer = PriceSerializer(update_price_status)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Price updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get price list
    @action(
        detail=False, methods=["get"], url_path="list"
    )
    def admin_list_prices(self, request):
        """List prices with pagination and search query"""
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

            promos = self.admin_service.admin_list_price(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=promos, message="Prices listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

