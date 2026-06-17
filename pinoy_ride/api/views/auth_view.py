from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema, OpenApiResponse
from api.utils.app_response import AppResponse
from api.services.user_service import UserService
from api.services.otp_service import OtpService
from api.utils.refresh_token_management import set_refresh_token_in_cookie, get_refresh_token_in_cookie, destroy_refresh_token_in_cookie
from api.utils.custom_error import AuthError, ValidationError, NotFoundError
from api.utils.views_swagger_decorator.auth_view_decorator import auth_schema,refresh_token_schema,logout_schema
from api.serializers import UserSerializer
from django.db import transaction

class AuthViewSet(viewsets.ViewSet):
    """Authentication Controller"""
    authentication_classes = []  # No authentication by default (login, etc. are public) 
    @auth_schema()
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """Authenticate user and return access token; set refresh token in cookies"""
        email = request.data.get("email")
        password = request.data.get("password")
        remember_me = request.data.get("remember_me", False)

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

            set_refresh_token_in_cookie(response, refresh_token, remember_me=remember_me)

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


    @action(detail=False, methods=['post'], url_path='fp-send-otp')
    def fp_send_otp(self, request):
        """Generate OTP"""
        
        try:

            # Validation
            email = request.data.get("email")

            user_service = UserService()
            otp_service = OtpService() 

            user_details = user_service.get_by_email(email=email)
            mobile_no  = user_details.mobile_no
        
            generate_data = {
                "mobile_no" : mobile_no,
                "user_type" : "admin"
            }

            # with transaction.atomic():
            otp_data = otp_service.generate_otp(generate_data)
                
            return AppResponse.send_success(data=otp_data, message="Otp sent successfully")


        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        # except Exception as e:

        #     return AppResponse.send_error(message=str(e), code=500)




    @action(detail=False, methods=['post'], url_path='fp-validate-otp')
    def fp_validate_otp(self, request):
        """Verify OTP"""
        
        try:

            # Validation
            email = request.data.get("email")
            otp_code = request.data.get("otp_code")

            if not otp_code:
                return AppResponse.send_error(message="Otp code is required", code=400)

            user_service = UserService()
            otp_service = OtpService() 

            user_details = user_service.get_by_email(email=email)
            mobile_no  = user_details.mobile_no

            verify_data = {
                "mobile_no" : mobile_no,
                "user_type" : "admin",
                "code" : otp_code
            }
                
            otp_data = otp_service.verify_otp(verify_data)

            return AppResponse.send_success(data=[], message="OTP verified!")



        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)




    @action(detail=False, methods=['post'], url_path='update-password')
    def update_password(self, request):
        """Update password """
        email = request.data.get("email")
        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        if password != confirm_password:
            return AppResponse.send_error(message="Password doesn't match!", code=400)
        
        try:
            user_service = UserService() 
            user_details = user_service.get_by_email(email=email)

            user_service.update_password(user_instance=user_details, new_password=password)

            return AppResponse.send_success(
                data={},
                message="Password updated successfully"
            )

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:

            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['get'], url_path='get_user_details', authentication_classes=[JWTAuthentication])
    def get_user_details(self, request):
        """Get current authenticated user details"""

        try:
            # User is authenticated via JWT, request.user contains the user
            user = request.user

            if not user or not user.is_authenticated:
                return AppResponse.send_error(message="User not authenticated", code=401)

            serializer = UserSerializer(user)

            return AppResponse.send_success(
                data=serializer.data,
                message="User details retrieved successfully"
            )

        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)


    @action(detail=False, methods=['post'], url_path='update_user_details', authentication_classes=[JWTAuthentication])
    def update_user_details(self, request):
        """Update current authenticated user details"""

        try:
            user = request.user

            if not user or not user.is_authenticated:
                return AppResponse.send_error(message="User not authenticated", code=401)

            user_service = UserService()

            # Prepare update data (exclude sensitive fields)
            user_data = {
                "first_name": request.data.get("first_name", user.first_name),
                "middle_name": request.data.get("middle_name", user.middle_name),
                "last_name": request.data.get("last_name", user.last_name),
                "position": request.data.get("position", user.position),
                "role": request.data.get("role", user.role),
                "mobile_no": request.data.get("mobile_no", user.mobile_no),
            }

            # Handle access field if provided
            if "access" in request.data:
                access_list = request.data.get("access", [])
                if isinstance(access_list, list):
                    user_data["access"] = access_list
                elif isinstance(access_list, str):
                    user_data["access"] = access_list.split("|")

            with transaction.atomic():
                updated_user = user_service.update_user(user, user_data)

            serializer = UserSerializer(updated_user)

            return AppResponse.send_success(
                data=serializer.data,
                message="User details updated successfully"
            )

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
            return AppResponse.send_error(message=str(e), code=500)