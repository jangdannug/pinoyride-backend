from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminRiderService,
    WalletService
)
from api.serializers import RiderSerializer, PartialRiderSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from api.utils.auth import get_authenticated_user


class AdminRiderViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Admin Rider
    """

    permission_classes = [IsAuthenticated]

    # lookup_field = 'code'

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminRiderService()
        self.wallet_service = WalletService()
        

    ## Get rider applicant list
    @action(
        detail=False, methods=["get"], url_path="applicant-list"
    )
    def admin_list_rider_applicants(self, request):
        """List rider applicants with pagination and search query"""
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

            riders = self.admin_service.admin_list_applicants(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=riders, message="Rider Applicants listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Get rider applicant by id
    @action(
        detail=False, methods=["get"], url_path="get-applicant"
    )
    def get_rider_applicant_by_id(self, request):
        """Retrieve rider applicant"""

        rider_id = request.query_params.get("rider_id", "")
        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        try:

            rider = self.admin_service.get_rider_applicant_by_id(rider_id)
            
            serializer = PartialRiderSerializer(rider)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Rider fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Update rider applicant status
    @action(
        detail=False, methods=["put"], url_path="update-applicant-status"
    )
    def update_applicant_status(self, request):
        """Update rider applicant status"""

        auth_user = get_authenticated_user(request)
        rider_id  = request.data.get("rider_id")
        applicant_status  = request.data.get("applicant_status")

        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        if not applicant_status:
            return AppResponse.send_error(message="Applicant Status is required!", code=400)
    
        try:
            with transaction.atomic():
                rider = self.admin_service.get_rider_applicant_by_id(rider_id=rider_id)

                update_applicant_status = self.admin_service.update_rider_applicant_status(rider=rider, applicant_status = applicant_status, auth_user_id=auth_user.id)

                serializer = RiderSerializer(update_applicant_status)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Rider applicant updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    
    ## Get riders list
    @action(
        detail=False, methods=["get"], url_path="get-list"
    )
    def admin_list_riders(self, request):
        """List active riders with pagination and search query"""
        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            name_filter = request.query_params.get("name_filter")
            current_location = request.query_params.get("current_location", None)
            vehicle_type = request.query_params.get("vehicle_type", None)
            vehicle_brand = request.query_params.get("vehicle_brand", None)

            filters = {}

            if name_filter:
                filters["name_filter"] = name_filter

            if current_location:
                filters["current_location"] = current_location

            if vehicle_type:
                filters["vehicle_type"] = vehicle_type

            if vehicle_brand:
                filters["vehicle_brand"] = vehicle_brand

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            riders = self.admin_service.admin_list_riders(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=riders, message="Riders listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
    ## Get rider booking history
    @action(
        detail=False, methods=["get"], url_path="get-history"
    )
    def admin_get_rider_booking_history(self, request):
        """List rider booking history with pagination and search query"""
        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            name_filter = request.query_params.get("name_filter")
            rider_id = request.query_params.get("rider_id", "")

            filters = {}

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            booking_history = self.admin_service.admin_list_rider_booking_history(
                rider_id=rider_id, page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )


            return AppResponse.send_success(
                data=booking_history, message="Rider booking history listed successfully", code=status.HTTP_200_OK
            )
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    ## Update rider status
    @action(
        detail=False, methods=["put"], url_path="update-status"
    )
    def update_rider_status(self, request):
        """Update rider status"""
        auth_user = get_authenticated_user(request)
        rider_id  = request.data.get("rider_id")
        rider_status  = request.data.get("status")

        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        if not rider_status:
            return AppResponse.send_error(message="Rider Status is required!", code=400)

        try:
            with transaction.atomic():
                rider = self.admin_service.get_rider_by_id(rider_id=rider_id)

                update_rider_status = self.admin_service.update_rider_status(rider=rider, rider_status = rider_status, auth_user_id=auth_user.id)

                serializer = RiderSerializer(update_rider_status)
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


    ## Get rider  by id
    @action(
        detail=False, methods=["get"], url_path="get-rider"
    )
    def get_rider_by_id(self, request):
        """Retrieve rider details"""

        rider_id = request.query_params.get("rider_id", "")
        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        try:

            rider = self.admin_service.get_rider_by_id(rider_id)
            
            serializer = RiderSerializer(rider)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Rider details fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    
    ## Delete rider
    @action(
        detail=False, methods=["post"], url_path="delete-rider"
    )
    def delete_rider(self, request):
        """Delete rider"""
        auth_user = get_authenticated_user(request)
        rider_id  = request.data.get("rider_id")

        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        try:
            with transaction.atomic():
                rider = self.admin_service.get_rider_by_id(rider_id=rider_id)

                delete_rider = self.admin_service.delete_rider(rider=rider, auth_user_id=auth_user.id)

                serializer = RiderSerializer(delete_rider)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Rider deleted successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    
    ## Get rider widthrawal history
    @action(
        detail=False, methods=["get"], url_path="get-widthrawal-history"
    )
    def admin_rider_widthrawal_history(self, request):
        """List rider widthrawal history  with pagination and search query"""
        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            name_filter = request.query_params.get("name_filter")
            rider_id = request.query_params.get("rider_id")

            if not rider_id:
                return AppResponse.send_error(message="Rider id is required", code=400)
            
            filters = {}

            if name_filter:
                filters["name_filter"] = name_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-updated_at"

            wallet_history = self.wallet_service.get_widthrawal_history(
                user_id=rider_id, user_type='rider',  page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=wallet_history, message="Rider's widthrawal history listed successfully"
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get rider current location
    @action(
        detail=False, methods=["get"], url_path="get-rider-location"
    )
    def get_rider_current_location(self, request):
        """Get rider current location"""

        rider_id = request.query_params.get("rider_id", "")
        if not rider_id:
            return AppResponse.send_error(message="Rider Id is required!", code=400)

        try:
            rider_location = self.admin_service.get_rider_current_location(rider_id=rider_id)

            return AppResponse.send_success(
                data=rider_location, message="Rider current location fetched successfully", code=status.HTTP_200_OK
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get all complaints
    @action(
        detail=False, methods=["get"], url_path="get-complaints"
    )
    def get_all_complaints(self, request):
        """Get rider complaints with pagination and search query"""
        try:
            rider_id = request.query_params.get("rider_id", "")
            if not rider_id:
                return AppResponse.send_error(message="Rider Id is required!", code=400)

            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 10))
            query = request.query_params.get("query", None)
            sort_by = request.query_params.get("sort_by")
            status_filter = request.query_params.get("status")
            user_type_filter = request.query_params.get("user_type")

            filters = {}

            filters["rider_id"] = rider_id

            if status_filter:
                filters["status"] = status_filter

            if user_type_filter:
                filters["user_type"] = user_type_filter

            if sort_by == "" or sort_by is None:
                sort_by = "-created_at"

            complaints = self.admin_service.get_all_complaints(
                page_number=page, page_size=perpage, search_query=query, filters=filters, sort_by=sort_by
            )

            return AppResponse.send_success(
                data=complaints, message="Rider complaints listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )