from django.db import transaction
from api.repositories import TaskRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
class AdminTaskService:
    
    def __init__(self):
        self.task = TaskRepository()

    
    ## Create task
    @transaction.atomic
    def create_task(self, task, auth_user_id):
        """Creates task"""
        
        new_task = self.task.create(task, auth_user_id)

        return new_task


    ## Get price by id
    def get_task_by_id(self,task_id):
        """Fetch price"""
        task = self.task.get_by_id(task_id=task_id)
        
        if task is None:
            raise NotFoundError("Task "+ str(task_id) + " not found")
        return task

    ## Update task
    @transaction.atomic
    def update_task(self, task, update_data, auth_user_id):
        """Update task"""

        update_task = self.task.update_task(task_instance=task, update_data=update_data, auth_user_id=auth_user_id)
    
        return update_task


    ## Update task status
    @transaction.atomic
    def update_task_status(self, task, task_status, auth_user_id):
        """Update task status"""

        update_task = self.task.update_task_status(task_instance=task, task_status=task_status, auth_user_id=auth_user_id)
    
        return update_task


    ## Admin get list of tasks
    def admin_list_tasks(self, auth_user_id, status):
        """List all tasks"""
        return self.task.admin_task_list(auth_user_id, status)
    

    ## Delete all tasks
    @transaction.atomic
    def delete_all_tasks(self, auth_user_id):
        """Delete all tasks"""

        delete_tasks = self.task.delete_all_tasks(auth_user_id=auth_user_id)
    
        return delete_tasks