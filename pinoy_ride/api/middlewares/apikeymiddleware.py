# myapp/middleware.py

from django.http import JsonResponse
from django.conf import settings
import os
from django.utils import timezone


class ApiKeyAuthenticationMiddleware:
    """
    Middleware to check for a valid API key in the request headers for API access.
    Also checks app version and returns update link if version is outdated.
    Separate version checking for customer and rider apps.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Customer routes and version settings
        self.customer_routes = ('/api/customers/',)
        self.customer_min_version = os.getenv('MIN_CUSTOMER_APP_VERSION', '1.0.0')
        self.customer_download_link = os.getenv('CUSTOMER_APP_DOWNLOAD_LINK', 'https://drive.google.com/customer')

        # Rider routes and version settings
        self.rider_routes = ('/api/riders/',)
        self.rider_min_version = os.getenv('MIN_RIDER_APP_VERSION', '1.0.0')
        self.rider_download_link = os.getenv('RIDER_APP_DOWNLOAD_LINK', 'https://drive.google.com/driver')

    def get_user_type_from_path(self, path, user_type=None):
        """Determine user type from request path or request data"""
        # First check if path is in customer_routes or rider_routes
        if path.startswith(self.customer_routes):
            return 'customer'
        elif path.startswith(self.rider_routes):
            return 'rider'

        # If not in routes, check if user_type field exists in request data
        if user_type:
            if user_type in ['customer', 'rider']:
                return user_type

        return None

    def get_min_app_version(self, user_type):
        """Get minimum app version from environment based on user type"""
        if user_type == 'customer':
            return self.customer_min_version
        elif user_type == 'rider':
            return self.rider_min_version
        return self.customer_min_version

    def get_download_link(self, user_type):
        """Get download link based on user type"""
        if user_type == 'customer':
            return self.customer_download_link
        elif user_type == 'rider':
            return self.rider_download_link
        return self.customer_download_link

    def compare_versions(self, current_version, min_version):
        """Compare two version strings (e.g., '1.0.0' < '1.2.3' returns True)"""
        try:
            current_parts = list(map(int, current_version.split('.')))
            min_parts = list(map(int, min_version.split('.')))

            # Pad shorter version with zeros
            max_length = max(len(current_parts), len(min_parts))
            current_parts += [0] * (max_length - len(current_parts))
            min_parts += [0] * (max_length - len(min_parts))

            # Compare each part
            for c, m in zip(current_parts, min_parts):
                if c < m:
                    return True  # Current version is less than minimum
                elif c > m:
                    return False  # Current version is greater than minimum

            return False  # Versions are equal
        except (ValueError, AttributeError):
            # If version parsing fails, return False (allow request)
            return False

    def __call__(self, request):

        if request.path.startswith('/api/') and settings.ENV != 'development':
            api_key_app = request.headers.get('X-API-KEY')
            api_key_callback = request.headers.get('api-key')

            api_routes = (
                '/api/customers/',
                '/api/riders/',
                '/api/booking/',
                '/api/otp/',
                '/api/qrph/',
                '/api/ekyc/',
                '/api/promo/',
                '/api/messages/'
            )

            callback_routes = (
                 '/api/ekyc/callback/',
                 '/api/qrph/callback/'
            )

            # Check callback routes (api-key)
            if request.path.startswith(callback_routes):
               if api_key_callback != settings.CALLBACK_API_KEY:
                    response = self.get_response(request)
                    return response

            # Check normal API routes (X-API-KEY)
            elif request.path.startswith(api_routes):
                if api_key_app != settings.CUSTOM_API_KEY:
                    return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)

                # Check app version from request data
                app_version = None
                request_data = None
                try:
                    if request.method == 'POST':
                        if request.content_type and 'multipart' in request.content_type:
                            # Use Django's request.POST for multipart/form-data
                            app_version = request.POST.get('app_version')
                            user_type = request.POST.get('user_type')
                            request_data = dict(request.POST)
                        elif request.content_type and 'json' in request.content_type:
                            # Parse JSON for application/json
                            import json
                            body_data = json.loads(request.body)
                            app_version = body_data.get('app_version')
                            user_type = request.POST.get('user_type')
                            request_data = body_data
                        elif request.content_type and 'application/x-www-form-urlencoded' in request.content_type:
                            # Use Django's request.POST for URL encoded
                            app_version = request.POST.get('app_version')
                            user_type = request.POST.get('user_type')
                            request_data = dict(request.POST)
                except Exception as e:
                    print(f"Error parsing app_version: {e}")
                    pass

                # Default app version
                if not app_version:
                    app_version = None

                # Determine user type from path and get corresponding version
                user_type = self.get_user_type_from_path(request.path, user_type)
              
                # Skip version check if user_type is None or app version is None
                if user_type is None or app_version is None:
                    response = self.get_response(request)
                    return response

                min_version = self.get_min_app_version(user_type)
                download_link = self.get_download_link(user_type)

                if app_version and self.compare_versions(app_version, min_version):
                    response_data = {
                        'status': 'error',
                        'ts': timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
                        'message': 'App version outdated. Please update to the latest version.',
                        'code': 426,
                        'data': {
                            'update_required': True,
                            'update_link': download_link,
                            'current_version': app_version,
                            'minimum_version': min_version,
                            'user_type': user_type
                        }
                    }
                    return JsonResponse(response_data, status=426)


        response = self.get_response(request)
        return response
