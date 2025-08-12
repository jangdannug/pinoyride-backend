from functools import wraps
from api.utils.app_response import AppResponse
from api.utils.custom_error import ForbiddenError, CustomError
from api.utils.auth import get_authenticated_user

def access_required(required_access):
    """
    Decorator to restrict access based on user access levels.
    Usage:
    @access_required(["ALL", "Beneficiary", "Claiming", "Verification])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(self, request, *args, **kwargs):
            
            try:
                user = get_authenticated_user(request)
                user_access = user.access
                
                if not any(access in user_access for access in required_access):
                    raise ForbiddenError("Access denied")

                return view_func(self, request, *args, **kwargs)
            
            except CustomError as e:
                return AppResponse.send_error(message=str(e.message), code=e.status_code)
            except Exception as e:
                return AppResponse.send_error(message="An unexpected error occurred", code=500)

                
        return wrapped_view
    return decorator
