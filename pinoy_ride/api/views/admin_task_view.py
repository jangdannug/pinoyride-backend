from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import json
from rest_framework.exceptions import ValidationError
from api.services import (
    AdminTaskService
)
from api.serializers import TaskSerializer
from api.utils.app_response import AppResponse
from api.utils.custom_error import CustomError, NotFoundError, ValidationError
from django.db import transaction
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import IsAuthenticated
from api.utils.auth import get_authenticated_user


class AdminTaskViewSet(viewsets.ViewSet):
    """
    ViewSet for managing Admin Tasks
    """

    permission_classes = [IsAuthenticated]

    # lookup_field = 'code'

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.admin_service = AdminTaskService()


    ## Add new task
    @action(
        detail=False, methods=["post"], url_path="create"
    )
    def add_task(self, request):
        """
        Add new task
        """

        try:
            auth_user = get_authenticated_user(request)

            task_name = request.data.get("task_name")
            if not task_name:
                return AppResponse.send_error(message="Task Name is required!", code=400)

            with transaction.atomic():
                task = self.admin_service.create_task(task = request.data, auth_user_id = auth_user.id)
                serializer = TaskSerializer(task)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Task added successfully", code=201
            )

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)



    ## Get task by id
    @action(
        detail=False, methods=["get"], url_path="get"
    )
    def get_task_by_id(self, request):
        """Retrieve task"""

        task_id = request.query_params.get("task_id", "")
        if not task_id:
            return AppResponse.send_error(message="Task Id is required!", code=400)

        try:

            task = self.admin_service.get_task_by_id(task_id)
            
            serializer = TaskSerializer(task)
            response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Task fetched successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



    ## Update task
    @action(
        detail=False, methods=["put"], url_path="update"
    )
    def update_task(self, request):
        """Update task"""
        task_id  = request.data.get("task_id")
        auth_user = get_authenticated_user(request)
        
        if not task_id:
            return AppResponse.send_error(message="Task Id is required!", code=400)
    
        try:
            with transaction.atomic():
                task = self.admin_service.get_task_by_id(task_id=task_id)

                task_serializer = TaskSerializer(instance=task, data=request.data)
                if not task_serializer.is_valid():
                    return AppResponse.send_error(message=task_serializer.errors, code=400)

                update_task = self.admin_service.update_task(task=task, update_data = request.data, auth_user_id = auth_user.id)

                serializer = TaskSerializer(update_task)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Task updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )




     ## Update task status
    @action(
        detail=False, methods=["put"], url_path="update_status"
    )
    def update_task_status(self, request):
        """Update task status"""
        task_id  = request.data.get("task_id")
        task_status  = request.data.get("status")
        auth_user = get_authenticated_user(request)
        allowed_status = ["0", "1"]

        if not task_id:
            return AppResponse.send_error(message="Task Id is required!", code=400)

        if not task_status:
            return AppResponse.send_error(message="Task Status is required!", code=400)

        if task_status not in allowed_status:
                return AppResponse.send_error(message="Invalid status "+str(task_status), code=400)
        try:
            with transaction.atomic():
                task = self.admin_service.get_task_by_id(task_id=task_id)

                update_task_status = self.admin_service.update_task_status(task=task, task_status = task_status, auth_user_id = auth_user.id)

                serializer = TaskSerializer(update_task_status)
                response_data = serializer.data

            return AppResponse.send_success(
                data=response_data, message="Task status updated successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    ## Get tasks list
    @action(
        detail=False, methods=["get"], url_path="list"
    )
    def admin_list_tasks(self, request):
        """List tasks """
        try:
            auth_user = get_authenticated_user(request)
            task_status = request.query_params.get("status", 0)

            tasks = self.admin_service.admin_list_tasks(auth_user_id=auth_user.id, status=task_status)

            return AppResponse.send_success(
                data=tasks, message="Task listed successfully", code=status.HTTP_200_OK
            )
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



     ## Delete all tasks
    @action(
        detail=False, methods=["put"], url_path="delete_all"
    )
    def delete_all_tssks(self, request):
        """Delete all tasks"""
        auth_user = get_authenticated_user(request)
        
        try:
            with transaction.atomic():

                self.admin_service.delete_all_tasks(auth_user_id = auth_user.id)

            return AppResponse.send_success(
                data=[], message="Tasks deleted successfully", code=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)
        except Exception as e:
            return AppResponse.send_error(
                message=str(e), code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )