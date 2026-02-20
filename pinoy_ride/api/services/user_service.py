from api.repositories.user_repository import UserRepository  # Corrected import
from api.utils.custom_error import AuthError, NotFoundError, ValidationError
from django.contrib.auth.hashers import make_password, check_password
from rest_framework_simplejwt.tokens import RefreshToken


class UserService:
    def __init__(self):
        self.user_repo = UserRepository()

    def create_user(self, user_data):
        """Create a new user with hashed password"""
        access_list = user_data.get("access", [])
        user_data["access"] = " | ".join(access_list)

        user_data["password"] = make_password(user_data.get("password"))
        user = self.user_repo.create(
            first_name=user_data.get("first_name"),
            middle_name=user_data.get("middle_name"),
            last_name=user_data.get("last_name"),
            email=user_data.get("email"),
            position=user_data.get("position"),
            role=user_data.get("role"),
            access=user_data.get("access"),
            password=user_data.get("password"),
        )
        return user

    def update_user(self, user, user_data):
        """Update user details excluding password"""
        access_list = user_data.get("access", [])
        user_data["access"] = " | ".join(access_list)

        updated_user_data = {
            "first_name": user_data.get("first_name"),
            "middle_name": user_data.get("middle_name"),
            "last_name": user_data.get("last_name"),
            "email": user_data.get("email"),
            "position": user_data.get("position"),
            "role": user_data.get("role"),
            "access": user_data.get("access"),
        }

        updated_user = self.user_repo.update(user, updated_user_data=updated_user_data)
        return updated_user

    def get_user_by_id(self, user_id):
        """Retrieve a user by their ID"""
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def delete_user(self, user_id):
        """Delete a user by their ID"""
        user = self.get_user_by_id(user_id)

        if user is None:
            raise NotFoundError("User not found")
        self.user_repo.delete(user)
        return True

    def auth(self, email, password):
        """Authenticate user and return JWT tokens"""
        user = self.user_repo.get_by_email(email)
        if user is None:
            raise AuthError("User not found")

        if not check_password(password, user.password):
            raise AuthError("Invalid credentials")

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access": user.access,
            "first_name" : user.first_name,
        }

    def refresh_token(self, refresh_token):
        """Refresh access token using refresh token"""
        if not refresh_token:
            raise AuthError("No refresh token provided")

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            return {"access_token": new_access_token}
        except Exception as e:
            raise AuthError("Invalid refresh token")

    def blacklist_refresh_token(self, refresh_token):
        """Blacklist a refresh token to prevent reuse"""
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return True
        except Exception as e:
            print(e)
            raise AuthError("Invalid refresh token")

    def list_users(self,current_user_id, page_number=1, page_size=10, search_query=None, type=None):
        """List all users"""

        if type and type == "all":
            return self.user_repo.all()

        return self.user_repo.list(current_user_id,page_number, page_size, search_query)
    
    def change_password(self, user_instance, password, new_password):
        """Authenticate user and return JWT tokens"""

        if not check_password(password, user_instance.password):
            raise ValidationError("Invalid password")
        
        hashed_password = make_password(new_password)
        user = self.user_repo.change_password(user=user_instance, new_password=hashed_password)
        return user
    

    def get_by_email(self, email):
        """Get User by email"""
        user = self.user_repo.get_by_email(email)
        if user is None:
            raise ValidationError("User not found")

        return user
    
    def update_password(self, user_instance, new_password):
        """Update user's password"""
        
        hashed_password = make_password(new_password)
        user = self.user_repo.change_password(user=user_instance, new_password=hashed_password)
        return user
    
