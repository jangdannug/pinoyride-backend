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
            api_key_customer = request.headers.get('X-API-KEY')
 
                            
            # if api_key_customer != settings.CUSTOM_API_KEY:
            #     return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)

        response = self.get_response(request)
        return response