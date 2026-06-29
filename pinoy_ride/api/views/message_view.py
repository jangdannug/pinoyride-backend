from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import MessageService
from api.serializers import MessageSerializer, SendMessageSerializer, MarkReadSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError as CustomValidationError
from django.db import transaction
from rest_framework.decorators import action


class MessageViewSet(viewsets.ViewSet):
    """
    ViewSet for managing chat messages between rider and customer.
    Uses X-API-KEY for authentication (handled by middleware).
    """

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_service = MessageService()

    @action(
        detail=False,
        methods=["post"],
        url_path="send"
    )
    @extend_schema(
        summary="Send a message",
        description="Send a message to a booking conversation",
        request=SendMessageSerializer,
        responses={200: OpenApiResponse(description="Message sent successfully")},
        tags=["Messages"]
    )
    def send_message(self, request):
        """Send a message to a booking conversation"""
        booking_id = request.data.get("booking_id")
        sender_id = request.data.get("sender_id")
        sender_type = request.data.get("sender_type", "customer")
        message_text = request.data.get("message_text")

        if not sender_id:
            return AppResponse.send_error(message="sender_id is required", code=400)

        try:
            with transaction.atomic():
                new_message = self.message_service.send_message(
                    booking_id=booking_id,
                    sender_id=sender_id,
                    sender_type=sender_type,
                    message_text=message_text
                )

                serializer = MessageSerializer(new_message, context={'current_user_id': sender_id})
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data,
                message="Message sent successfully",
                code=status.HTTP_200_OK
            )

        except CustomValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="conversation"
    )
    @extend_schema(
        summary="Get conversation history",
        description="Get conversation history for a booking with pagination",
        parameters=[
            OpenApiParameter(name="booking_id", type=int, required=True, description="Booking ID"),
            OpenApiParameter(name="user_id", type=int, required=True, description="User ID (to determine is_sent_by_me)"),
            OpenApiParameter(name="user_type", type=str, required=True, description="User type (customer/rider)"),
            OpenApiParameter(name="page", type=int, required=False, description="Page number (default: 1)"),
            OpenApiParameter(name="perpage", type=int, required=False, description="Items per page (default: 50)"),
            OpenApiParameter(name="last_seen_id", type=int, required=False, description="Get messages after this ID"),
        ],
        responses={200: OpenApiResponse(description="Conversation retrieved successfully")},
        tags=["Messages"]
    )
    def get_conversation(self, request):
        """Get conversation history for a booking"""
        booking_id = request.query_params.get("booking_id", "")
        user_id = request.query_params.get("user_id", "")
        user_type = request.query_params.get("user_type", "")

        if not booking_id:
            return AppResponse.send_error(message="Booking ID is required", code=400)
        if not user_id:
            return AppResponse.send_error(message="User ID is required", code=400)
        if not user_type:
            return AppResponse.send_error(message="User type is required", code=400)

        try:
            page = int(request.query_params.get("page", 1))
            perpage = int(request.query_params.get("perpage", 50))
            last_seen_id = request.query_params.get("last_seen_id", None)

            if last_seen_id:
                last_seen_id = int(last_seen_id)

            messages = self.message_service.get_conversation(
                booking_id=int(booking_id),
                page_number=page,
                page_size=perpage,
                last_seen_id=last_seen_id
            )

            # Add is_sent_by_me to each message
            # Must check BOTH sender_id AND sender_type to avoid conflicts
            for msg in messages['data']:
                msg['is_sent_by_me'] = (msg['sender'] == int(user_id) and msg['sender_type'] == user_type)

            return AppResponse.send_success(
                data=messages,
                message="Conversation retrieved successfully",
                code=status.HTTP_200_OK
            )

        except CustomValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=["put"],
        url_path="mark-read"
    )
    @extend_schema(
        summary="Mark messages as read",
        description="Mark all unread messages as read for a user",
        request=MarkReadSerializer,
        responses={200: OpenApiResponse(description="Messages marked as read")},
        tags=["Messages"]
    )
    def mark_as_read(self, request):
        """Mark messages as read for a user"""
        booking_id = request.data.get("booking_id")
        user_id = request.data.get("user_id")
        user_type = request.data.get("user_type")

        if not booking_id:
            return AppResponse.send_error(message="Booking ID is required", code=400)
        if not user_id:
            return AppResponse.send_error(message="User ID is required", code=400)
        if not user_type:
            return AppResponse.send_error(message="User type is required", code=400)

        try:
            with transaction.atomic():
                result = self.message_service.mark_messages_read(
                    booking_id=int(booking_id),
                    user_id=int(user_id),
                    user_type=user_type
                )

            return AppResponse.send_success(
                data=result,
                message="Messages marked as read successfully",
                code=status.HTTP_200_OK
            )

        except CustomValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count"
    )
    @extend_schema(
        summary="Get unread message count",
        description="Get count of unread messages for a booking",
        parameters=[
            OpenApiParameter(name="booking_id", type=int, required=True, description="Booking ID"),
            OpenApiParameter(name="user_id", type=int, required=True, description="User ID"),
            OpenApiParameter(name="user_type", type=str, required=False, description="User type (customer/rider)"),
        ],
        responses={200: OpenApiResponse(description="Unread count retrieved successfully")},
        tags=["Messages"]
    )
    def get_unread_count(self, request):
        """Get count of unread messages for a user"""
        booking_id = request.query_params.get("booking_id", "")
        user_id = request.query_params.get("user_id", "")
        user_type = request.query_params.get("user_type", "")

        if not booking_id:
            return AppResponse.send_error(message="Booking ID is required", code=400)
        if not user_id:
            return AppResponse.send_error(message="User ID is required", code=400)

        try:
            result = self.message_service.get_unread_count(
                booking_id=int(booking_id),
                user_id=int(user_id),
                user_type=user_type
            )

            return AppResponse.send_success(
                data=result,
                message="Unread count retrieved successfully",
                code=status.HTTP_200_OK
            )

        except CustomValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
