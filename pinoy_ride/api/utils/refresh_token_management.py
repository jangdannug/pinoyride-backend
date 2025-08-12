from rest_framework.response import Response

def set_refresh_token_in_cookie(response: Response, refresh_token: str):
    """
    Set the refresh token in the response cookies.
    """
    response.set_cookie('refresh_token', refresh_token, httponly=True)

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