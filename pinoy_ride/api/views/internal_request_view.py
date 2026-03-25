from rest_framework import viewsets
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from api.utils.app_response import AppResponse
from django.db import transaction
from api.utils.custom_error import CustomError, NotFoundError, ValidationError

class InternalRequestViewSet(viewsets.ViewSet):
    """Internal Request Controller"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, request):
        """Request Get View"""

        try:            
            return AppResponse.send_success(data=[], message="Success")

        except NotFoundError as e:
            return AppResponse.send_error(message=str(e), code=404)

        except ValidationError as e:
            return AppResponse.send_error(message=str(e), code=400)

        except Exception as e:
             
            return AppResponse.send_error(message=str(e), code=500)    
        
    