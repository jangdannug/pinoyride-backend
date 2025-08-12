import json
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiRequest
from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.types import OpenApiTypes

def customer_create_schema():
    return extend_schema(
        tags=["Customer"],
        summary="Create a new Custotmer",
        description="Creates a new Customer",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "format": "json",
                        "description": "JSON object containing the Customer details",
                        "example": json.dumps({
                            "code": "0001",
                            "customer_type": "1",
                            "fname": "John",
                            "mname": "Smith",
                            "lname": "Doe",
                            "mobile": "639465221959",
                            "email": "user_001@example.com"
                        }, indent=2)
                    }
                }
            }
        },
        responses = {
    201: {
        "description": "Customer created successfully",
        "content": {
            "application/json": {
                "example": {
                    "status": "success",
                    "message": "Customer created successfully",
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
                        "first_name": ["This field is required."],
                        "email": ["Enter a valid email address."]
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
,  
    )
    
def customer_retrieve_decorator():
    return extend_schema(
        tags=["Customer"],
        summary="Retrieve a single Customer record",
        description="Retrieve a single Customer record",
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

def customer_update_schema():
    return extend_schema(
        tags=["Customer"],
        summary="Update an existing Customer",
        description="Updates an existing Customer with contacts, addresses, documents, and representatives. Image and documents are automatically handled by Django.",
        parameters=[
            {
                "name": "beneficiary_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "The ID of the Customer to update"
            }
        ],
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "string",
                        "format": "json",
                        "description": "JSON object containing updated Customer details",
                        "example": json.dumps({
                            "code": "0001",
                            "customer_type": "1",
                            "fname": "John1",
                            "mname": "Smith1",
                            "lname": "Doe1",
                            "mobile": "639465221959",
                            "email": "user_001@example.com"
                        }, indent=2)
                    }
                }
            }
        },
        responses={
            200: {
                "description": "Customer updated successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "message": "Customer updated successfully",
                            "data": {
                                "beneficiary_id": 1,
                                "first_name": "John",
                                "last_name": "Smith",
                                "image": "path/to/updated/image.jpg",
                                "documents": [
                                    {"file": "path/to/updated/document1.pdf", "file_name": "updated_medical_report1.png"},
                                    {"file": "path/to/updated/document2.pdf", "file_name": "updated_medical_report2.jpg"}
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
                                "first_name": ["This field is required."],
                                "email": ["Enter a valid email address."]
                            }
                        }
                    }
                }
            },
            404: {
                "description": "Customer not found",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "error",
                            "message": "Customer not found",
                            "data": None
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

def customer_delete_schema():
    return extend_schema(
        tags=["Customer"],
        summary="Delete a Customer",
        description="Soft deletes a Customer and optionally soft deletes related data",
        parameters=[
            {
                "name": "pk",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "The ID of the Customer to delete"
            }
        ],
        responses={
            200: {
                "description": "Customer deleted successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "message": "Deleted successfully"
                        }
                    }
                }
            },
            404: {
                "description": "Customer not found",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "error",
                            "message": "Beneficiary not found",
                            "data": None
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
                            "message": "Invalid beneficiary ID"
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



def customer_list_schema():
    return extend_schema(
        tags=["Customer"],
        summary="List of Customer",
        description="Retrieve a paginated list of customers with optional search and filters.",
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
                description="Number of customers per page (default: 10)",
                default=10
            ),
            OpenApiParameter(
                name="query",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Search customers by name, email, or contact number",
            ),
        ],
        request=OpenApiRequest(
            OpenApiTypes.OBJECT,
            examples=[
                {
                    "name": "Example Filters",
                    "summary": "Filtering Customers",
                    "value": {
                        "status": "Active",
                        "type_of_assistance": "Medical Assistance"
                    }
                }
            ]
        ),
        responses={
            200: OpenApiResponse(
                response=[],  
                description="Successfully retrieved paginated list of customers",
            ),
            400: OpenApiResponse(description="Invalid request parameters"),
            500: OpenApiResponse(description="Internal server error"),
        },
    )


def customer_details_decorator():
    return extend_schema(
        tags=["Customer"],
        summary="Get Customer details",
        description="Get Customer details",
        parameters=[
            OpenApiParameter(
                name="code",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="code",
                default=""
            )
        ],
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