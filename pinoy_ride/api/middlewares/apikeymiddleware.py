# myapp/middleware.py

from django.http import JsonResponse
from django.conf import settings

class ApiKeyAuthenticationMiddleware:
    """
    Middleware to check for a valid API key in the request headers for API access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

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
            )

            callback_routes = (
                 '/api/ekyc/callback/',
                 '/api/qrph/callback/'
            )

            # if request.path.startswith(api_routes):
            
            #    if api_key_app != settings.CUSTOM_API_KEY:
            #             return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)
               
             # Check callback routes (api-key)
            # if request.path.startswith(callback_routes):
            #    if api_key_callback != settings.CALLBACK_API_KEY:
                    # return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)

            # Check normal API routes (X-API-KEY)
            if request.path.startswith(api_routes):
                if api_key_app != settings.CUSTOM_API_KEY:
                    return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)


        response = self.get_response(request)
        return response