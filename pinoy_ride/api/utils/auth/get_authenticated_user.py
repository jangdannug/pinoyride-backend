from api.utils.custom_error import AuthError

def get_authenticated_user(request):
    user = request.user

    if not user or not user.is_authenticated:
        raise AuthError("User not authenticated")
    
    user.access = user.access.split(' | ')
    return user