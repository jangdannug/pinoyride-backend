from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from api.models.user_model import User  
from api.serializers.user_serializer import UserSerializer

class UserRepository:
    
    @staticmethod
    def get_by_email(email):
        try:
            user = User.objects.get(email=email, deleted_at__isnull=True)
            return user
        except User.DoesNotExist:
            return None
        
    @staticmethod
    def get_by_id(user_id):
        try:
            return User.objects.get(id=user_id, deleted_at__isnull=True)
        except User.DoesNotExist:
            return None

    @staticmethod
    def create(**kwargs):
        user = User(
            first_name=kwargs.get('first_name'),
            middle_name=kwargs.get('middle_name'),
            last_name=kwargs.get('last_name'),
            email=kwargs.get('email'),
            position=kwargs.get('position'),
            role=kwargs.get('role'),
            access=kwargs.get('access'),
            password=kwargs.get('password'),
            is_active=1
        )
        user.save()
        return user

    @staticmethod
    def update(user, updated_user_data):
        if user:
            user.first_name = updated_user_data.get('first_name')
            user.middle_name = updated_user_data.get('middle_name')
            user.last_name = updated_user_data.get('last_name')
            # user.email = updated_user_data.get('email')
            # user.position = updated_user_data.get('position')
            # user.role = updated_user_data.get('role')
            user.mobile_no = updated_user_data.get('mobile_no')
            user.access = updated_user_data.get('access')

            user.save()
            return user
        return None
    
    @staticmethod
    def change_password(user, new_password):
        if user:
            user.password = new_password
            user.save()
            return user
        return None

    @staticmethod
    def delete(user):
        user.deleted_at = timezone.now()
        user.save()
        return True
       
    @staticmethod
    def list(current_user_id, page_number=1, page_size=10, search_query=None, ):
        """Retrieve paginated users with optional search query"""
        users = User.objects.annotate(
            full_name=Concat(
                'first_name', Value(' '), 'middle_name', Value(' '), 'last_name'
            )
        ).filter(deleted_at__isnull=True).exclude(id=current_user_id).order_by("-id") 

        if search_query:
            search_terms = search_query.split() 
            query_filter = Q()
            for term in search_terms:
                query_filter |= (
                    Q(full_name__icontains=term) | 
                    Q(email__icontains=term) |
                    Q(position__icontains=term) |
                    Q(role__icontains=term)
                )
            users = users.filter(query_filter)

    
        paginator = Paginator(users, page_size)
        page = paginator.get_page(page_number)

        serialized_users = UserSerializer(page.object_list, many=True).data

        return {
            'users': serialized_users,
            'total_pages': paginator.num_pages,
            'current_page': page_number,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
            'next_page': page.next_page_number() if page.has_next() else None,
            'previous_page': page.previous_page_number() if page.has_previous() else None
        }
        
        
    @staticmethod
    def all():
        """Retrieve paginated users with optional search query"""
        users = User.objects.filter(deleted_at__isnull=True).order_by("-id")
        serialized_users = UserSerializer(users, many=True).data


        return {
            'users': serialized_users
        }
        

