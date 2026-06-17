from drf_spectacular.utils import extend_schema, OpenApiResponse

def auth_schema():
    return extend_schema(
        tags=["Authentication"],
        summary="User Authentication",
        description="Authenticates a user and returns an access token. The refresh token is set in an HTTP-only cookie. Use 'remember_me' to keep the session active for 7 days.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email", "description": "User's email", "example": "jd@email.com"},
                    "password": {"type": "string", "format": "password", "description": "User's password", "example": "password"},
                    "remember_me": {"type": "boolean", "description": "Keep session active for 7 days", "example": True},
                },
                "required": ["email", "password"],
            }
        },
        responses={
            200: OpenApiResponse(
                response={"access_token": "your-access-token"},
                description="Authentication successful",
            ),
            401: OpenApiResponse(description="Authentication failed"),
        },
    )

def refresh_token_schema():
    return extend_schema(
        tags=["Authentication"],  
        summary="Refresh Access Token",
        description="Uses the refresh token stored in cookies to generate a new access token.",
        responses={
            200: OpenApiResponse(
                response={"access_token": "new-access-token"},
                description="Access token refreshed",
            ),
            401: OpenApiResponse(description="Invalid or missing refresh token"),
        },
    )

def logout_schema():
    return extend_schema(
        tags=["Authentication"],  
        summary="User Logout",
        description="Logs out the user by blacklisting the refresh token and clearing it from cookies.",
        responses={
            200: OpenApiResponse(
                response={"message": "Logout successful"},
                description="Successfully logged out",
            ),
            400: OpenApiResponse(description="No refresh token provided"),
            401: OpenApiResponse(description="Invalid refresh token"),
        },
    )