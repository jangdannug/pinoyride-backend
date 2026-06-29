# myapp/middleware.py

from django.http import JsonResponse
from django.conf import settings
import os
from django.utils import timezone


class ApiKeyAuthenticationMiddleware:
    """
    Middleware to check for a valid API key in the request headers for API access.
    Also checks app version and returns update link if version is outdated.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Get update link from settings (this rarely changes)
        self.app_update_link = os.getenv('APP_DOWNLOAD_LINK', 'https://drive.google.com/')

    def get_min_app_version(self):
        """Get minimum app version from environment (reads dynamically)"""
        return os.getenv('MIN_APP_VERSION', '1.0.0')

    def compare_versions(self, current_version, min_version):
        """Compare two version strings (e.g., '1.0.0' <= '1.2.3' returns True)"""
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

            return True  # Versions are equal
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

            # if request.path.startswith(api_routes):

            #    if api_key_app != settings.CUSTOM_API_KEY:
            #             return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)

             # Check callback routes (api-key)
            if request.path.startswith(callback_routes):
               if api_key_callback != settings.CALLBACK_API_KEY:
                    # return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)
                    response = self.get_response(request)
                    return response

            # Check normal API routes (X-API-KEY)
            elif request.path.startswith(api_routes):
                if api_key_app != settings.CUSTOM_API_KEY:
                    return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)
                
                # Check app version from request data
                app_version = None
                try:
                    if request.method == 'POST':
                        if request.content_type and 'multipart' in request.content_type:
                            # Use Django's request.POST for multipart/form-data
                            app_version = request.POST.get('app_version')
                        elif request.content_type and 'json' in request.content_type:
                            # Parse JSON for application/json
                            import json
                            body_data = json.loads(request.body)
                            app_version = body_data.get('app_version')
                        elif request.content_type and 'application/x-www-form-urlencoded' in request.content_type:
                            # Use Django's request.POST for URL encoded
                            app_version = request.POST.get('app_version')
                except Exception as e:
                    print(f"Error parsing app_version: {e}")
                    pass
                
                # Default app version
                if not app_version:
                    app_version = '1.0.0'

                min_version = self.get_min_app_version()
                if app_version and self.compare_versions(app_version, min_version):
                    response_data = {
                        'status': 'error',
                        'ts': timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
                        'message': 'App version outdated. Please update to the latest version.',
                        'code': 426,
                        'data': {
                            'update_required': True,
                            'update_link': self.app_update_link,
                            'current_version': app_version,
                            'minimum_version': min_version
                        }
                    }
                    return JsonResponse(response_data, status=426)


        response = self.get_response(request)
        return response