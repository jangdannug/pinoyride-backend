from rest_framework import serializers
from ..models.user_model import User
from api.utils.enums.access_enums import AccessEnum
from api.utils.enums.roles_enums import RolesEnum

class UserSerializer(serializers.ModelSerializer):
    access = serializers.ListField(
        child=serializers.CharField(max_length=255),
        write_only=False
    )

    class Meta:
        model = User
        fields = ['id','first_name', 'middle_name', 'last_name', 'email', 'position', 
                  'role', 'access', 'created_at', 'updated_at', 'deleted_at']
        
    def to_representation(self, instance):
        """Ensure `access` is properly formatted as a list"""
        data = super().to_representation(instance)

        if isinstance(instance.access, str):
            data['access'] = instance.access.split('|')  

        return data

    def validate_access(self, value):
        """Validate the access field to ensure it contains valid values"""
        valid_access_values = {access.value.lower(): access.value for access in AccessEnum}
        normalized_access = []
        for access in value:
            if access.lower() not in valid_access_values:
                raise serializers.ValidationError(f"Invalid access value: {access}")
            normalized_access.append(valid_access_values[access.lower()])
        return normalized_access

    def validate_role(self, value):
        """Validate the role field to ensure it contains a valid value"""
        valid_role_values = [role.value for role in RolesEnum]
        if value not in valid_role_values:
            raise serializers.ValidationError(f"Invalid role value: {value}")
        return value

    def validate_email(self, value):
        """Validate the email field to ensure it is unique"""
        queryset = User.objects.filter(email=value, deleted_at__isnull=True)
        
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
