from rest_framework.response import Response

def set_refresh_token_in_cookie(response: Response, refresh_token: str, remember_me: bool = False):
    """
    Set the refresh token in the response cookies.

    Args:
        response: The HTTP response object
        refresh_token: The JWT refresh token
        remember_me: If True, cookie persists for 7 days. If False, it's a session cookie.
    """
    # If remember_me is True, set max_age to 7 days (604800 seconds)
    # If False, don't set max_age (session cookie - deleted when browser closes)
    if remember_me:
        # 7 days in seconds = 7 * 24 * 60 * 60 = 604800
        max_age = 7 * 24 * 60 * 60
        response.set_cookie('refresh_token', refresh_token, httponly=True, max_age=max_age, samesite='Lax')
    else:
        response.set_cookie('refresh_token', refresh_token, httponly=True, samesite='Lax')

def get_refresh_token_in_cookie(request):
    """
    Get the refresh token from the request cookies.
    """
    return request.COOKIES.get('refresh_token')

def destroy_refresh_token_in_cookie(response: Response):
    """
    Destroy the refresh token by setting an empty value and an expired max age.
    """
    response.delete_cookie('refresh_token')