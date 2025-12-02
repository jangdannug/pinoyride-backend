from django.db import transaction
from api.models import Customer
import datetime
from api.models import (
    Tasks,
)
from django.db.models import Func, F, Value, CharField
from django.forms.models import model_to_dict
from django.core.paginator import Paginator
from django.db.models import Q, Max, Value, OuterRef, Subquery, Prefetch
from django.db.models.functions import Concat
from django.utils.timezone import now
from datetime import timedelta
from api.serializers import (
    TaskSerializer
)


class TaskRepository:
   
    @staticmethod
    @transaction.atomic
    def create(task, auth_user_id):
        """Creates new task."""

        return Tasks.objects.create(
            task_name=task.get("task_name", ""),
            task_description=task.get("task_name", ""),
            added_by=auth_user_id
        )
    

    @staticmethod
    def get_by_id(task_id):
        """Fetch task"""
        try:
            return Tasks.objects.get(id=task_id)
        except Tasks.DoesNotExist:
            return None


    @staticmethod
    @transaction.atomic
    def update_task(task_instance, update_data, auth_user_id):
        
        task_instance.task_name = update_data.get("task_name", "")
        task_instance.task_description = update_data.get("task_name", "")
        task_instance.updated_by = auth_user_id
        task_instance.save()

        return task_instance


    @staticmethod
    @transaction.atomic
    def update_task_status(task_instance, task_status, auth_user_id):
        
        task_instance.status = task_status
        task_instance.updated_by = auth_user_id
        task_instance.save()
        
        return task_instance

    
    @staticmethod
    def admin_task_list(auth_user_id, status=0):
        """Retrieve tasks"""

        tasks = (
            Tasks.objects
            .filter(added_by=auth_user_id, status=status)
            .annotate()
            .order_by('-id')
        )

        serialized_tasks = TaskSerializer(
            tasks, many=True
        ).data

        return {
            "tasks": serialized_tasks,
        }
    

    @staticmethod
    @transaction.atomic
    def delete_all_tasks(auth_user_id):
        
        return Tasks.objects.filter(added_by=auth_user_id).update(status=1, updated_by=auth_user_id)