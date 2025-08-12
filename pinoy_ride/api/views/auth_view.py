from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiResponse
from api.utils.app_response import AppResponse
from api.services.user_service import UserService
from api.utils.refresh_token_management import set_refresh_token_in_cookie, get_refresh_token_in_cookie, destroy_refresh_token_in_cookie
from api.utils.custom_error import AuthError
from api.utils.views_swagger_decorator.auth_view_decorator import auth_schema,refresh_token_schema,logout_schema

class AuthViewSet(viewsets.ViewSet):
    """Authentication Controller"""
    authentication_classes = [] 
    @auth_schema()
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """Authenticate user and return access token; set refresh token in cookies"""
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return AppResponse.send_error(message="Email and password are required", code=400)

        try:
            user_service = UserService() 
            auth_response = user_service.auth(email, password)
            access_token = auth_response["access_token"]
            refresh_token = auth_response["refresh_token"]
            first_name = auth_response["first_name"]

            response = AppResponse.send_success(
                data={"access_token": access_token, "user" : first_name},
                message="Authentication successful"
            )
            
            set_refresh_token_in_cookie(response, refresh_token)

            return response

        except AuthError as e:
            return AppResponse.send_error(message="Invalid Credentials", code=401)

        except Exception as e:
            return AppResponse.send_error(message="An unexpected error occurred", code=500)

    @refresh_token_schema()
    @action(detail=False, methods=['get'], url_path='refresh')
    def refresh(self, request):
        """Refresh access token using refresh token stored in cookies"""
        refresh_token = get_refresh_token_in_cookie(request)

        if not refresh_token:
            return AppResponse.send_error(message="No refresh token found", code=401)

        try:
            user_service = UserService() 
            new_access_token = user_service.refresh_token(refresh_token)["access_token"]

            return AppResponse.send_success(
                data={"access_token": new_access_token},
                message="Access token refreshed"
            )
        except AuthError:
            return AppResponse.send_error(message="Invalid refresh token", code=401)

    @logout_schema()
    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        """Logs out the user by blacklisting the refresh token"""
        try:
            refresh_token = get_refresh_token_in_cookie(request)

            if not refresh_token:
                return AppResponse.send_error(message="No refresh token found", code=400)

            user_service = UserService()
            revoke = user_service.blacklist_refresh_token(refresh_token)

            if revoke:
                response = AppResponse.send_success(message="Logout successful")
                destroy_refresh_token_in_cookie(response)
                return response
        except AuthError:
            return AppResponse.send_error(message="Invalid refresh token", code=401)
