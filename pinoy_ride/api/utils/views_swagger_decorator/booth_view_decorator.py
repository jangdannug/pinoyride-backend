import json
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiRequest
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

def booth_get_list_view_decorator():
    return extend_schema(
        tags=["Booth"],
        summary="List of Booths",
        description="Retrieve a paginated list of booth with optional search and filters.",
        parameters=[
            OpenApiParameter(
                name="customer_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Page number (default: 1)",
                default=1
            )
        ],
        responses={
            200: OpenApiResponse(
                response={},
                description="Successfully retrieved paginated list of booths",
            ),
            400: OpenApiResponse(description="Invalid request parameters"),
            500: OpenApiResponse(description="Internal server error"),
        },
    )


def booth_populate_view_decorator():
    return extend_schema(
        tags=["Booth"],
        summary="Populate booth table",
        description="Populate booth table",
        responses = {
            200: {
                "description": "Customer retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "message": "Customer retrieved successfully",
                            "data": {
                                "beneficiary_id": 1,
                                "first_name": "John",
                                "last_name": "Smith",
                                "image": "path/to/uploaded/image.jpg",
                                "documents": [
                                    {"file": "path/to/uploaded/document1.pdf", "file_name": "medical_report1.png"},
                                    {"file": "path/to/uploaded/document2.pdf", "file_name": "medical_report2.jpg"}
                                ]
                            }
                        }
                    }
                }
            },
            400: {
                "description": "Invalid input data",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "error",
                            "message": "Invalid input data",
                            "data": {
                                "beneficiary_id": ["This field is required."]
                            }
                        }
                    }
                }
            },
            500: {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "error",
                            "message": "An unexpected error occurred. Please try again later.",
                            "data": None
                        }
                    }
                }
            }
        }
    )