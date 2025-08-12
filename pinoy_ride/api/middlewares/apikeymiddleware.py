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
            api_key = request.headers.get('X-API-KEY')  
            api_key_customer = request.headers.get('X-API-KEY')
            is_auditor = request.GET.get('is_auditor', '0')

            if request.path.startswith('/api/customer/') or request.path.startswith('/api/auditor/'):
                
                exceptions_routes = [
                    '/api/customer/get_schedule/',
                    '/api/customer/details/',
                    '/api/customer/get_details/',
                    '/api/customer/get_details_by_hash_code/',
                    '/api/customer/get_all/',
                    '/api/customer/health_check/',
                    '/api/customer/booth/populate_booth_products/',
                    '/api/customer/booth/populate_booth/',
                    '/api/customer/booth/populate_map/',
                    '/api/customer/souvenir/populate_souvenir/',
                    '/api/customer/populate_customer/',
                    '/api/customer/send_email_job/',
                    '/api/customer/check_closed_booths_job/',
                    '/api/customer/export-deal-carts/'
                ]
                              
                if api_key_customer != settings.CUSTOM_API_KEY:
                    return JsonResponse({'message': 'Invalid API key, Unauthorized Access'}, status=403)

        response = self.get_response(request)
        return response