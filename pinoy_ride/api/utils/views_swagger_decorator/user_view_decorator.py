from drf_spectacular.utils import extend_schema, OpenApiResponse
from api.serializers import UserSerializer
from drf_spectacular.utils import OpenApiParameter

def user_profile_schema():
    return extend_schema(
        tags=["User"],
        summary="Get User Profile",
        description="Returns the authenticated user's profile information.",
        responses={
            200: {
                "description": "User profile details",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "data": {
                                "id": 1,
                                "email": "jd@email.com",
                                "first_name": "John",
                                "last_name": "Doe",
                                "position": "Admin",
                                "role": "Super Admin",
                                "access": "All"
                            },
                            "message": "User profile retrieved successfully"
                        }
                    }
                }
            },
            401: {"description": "User not authenticated"},
        },
    )
    
def user_create_schema():
    return extend_schema(
        tags=["User"],
         summary="Create a new user",
        description="Create a new user",
        request=UserSerializer,
        responses={
            201: {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "id": 1,
                            "email": "jd@email.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "position": "Admin",
                            "role": "Super Admin",
                            "access": "All"
                        },
                        "message": "User created successfully"
                    }
                }
            },
            400: {"description": "Bad request"},
        },
    )
    
    
def user_update_schema():
    return extend_schema(
        tags=["User"],
         summary="Update an existing user",
        description="Update an existing user",
        request=UserSerializer,
        responses={
            200: {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "id": 1,
                            "email": "jd@email.com",
                            "first_name": "John",
                            "last_name": "Doe",
                            "position": "Admin",
                            "role": "Super Admin",
                            "access": "All"
                        },
                        "message": "User updated successfully"
                    }
                }
            },
            400: {"description": "Bad request"},
            404: {"description": "User not found"},
        },
    )
    
def user_retrieve_schema():
        return extend_schema(
            tags=["User"],
            summary="Retrieve User by ID",
            description="Retrieve a user by their ID.",
            responses={
                200: {
                    "description": "User details",
                    "content": {
                        "application/json": {
                            "example": {
                                "status": "success",
                                "data": {
                                    "id": 1,
                                    "email": "jd@email.com",
                                    "first_name": "John",
                                    "last_name": "Doe",
                                    "position": "Admin",
                                    "role": "Super Admin",
                                    "access": "All"
                                },
                                "message": "User retrieved successfully"
                            }
                        }
                    }
                },
                400: {"description": "Bad request"},
                404: {"description": "User not found"},
                500: {"description": "An unexpected error occurred"},
            },
        )

def user_delete_schema():
            return extend_schema(
                tags=["User"],
                summary="Delete a user by ID",
                description="Delete a user by their ID.",
                responses={
                    204: {
                        "description": "User deleted successfully",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "User deleted successfully"
                                }
                            }
                        }
                    },
                    400: {"description": "Bad request"},
                    404: {"description": "User not found"},
                    500: {"description": "An unexpected error occurred"},
                },
            )
            

def user_list_schema():
      return extend_schema(
    tags=["User"],
    summary="List users",
    description="List users with pagination and search query",
    parameters=[
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Page number (default: 1)",
            default=1
        ),
        OpenApiParameter(
            name="perpage",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Number of users per page (default: 10)",
            default=10
        ),
        OpenApiParameter(
            name="query",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Search query for filtering users",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=UserSerializer(many=True),  
            description="Successfully retrieved paginated list of users",
        ),
        400: OpenApiResponse(description="Invalid request parameters"),
        500: OpenApiResponse(description="Internal server error"),
    },
)