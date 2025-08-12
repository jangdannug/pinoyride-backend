# your_app/utils/responses.py
from rest_framework.response import Response
from rest_framework import status as http_status

class AppResponse:
    @staticmethod
    def send_success(data=None, message="Request successful", code=http_status.HTTP_200_OK, total_results=None):
        response = {
            "status": "success",
            "message": message,
            "code": code,
            "data": data
        }
        if total_results is not None:
            response["totalResults"] = total_results
        return Response(response, status=code)
    
    @staticmethod
    def send_error(data=None, message="An error occurred", code=http_status.HTTP_400_BAD_REQUEST):
        response = {
            "status": "error",
            "message": message,
            "code": code,
            "data": data
        }
        return Response(response, status=code)
