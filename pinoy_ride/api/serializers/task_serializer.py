from rest_framework import serializers
from api.models import Tasks

class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tasks
        fields = [
            "id",
            "task_name",
            "task_description",
            "status",
            "added_by",
            "updated_by",
            "created_at"
        ]