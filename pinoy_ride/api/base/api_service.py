from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
import requests
from api.utils.app_logger import app_logger

class ApiService:
    
    def __init__(self):
        self.customer = CustomerRepository()
    

    @staticmethod
    def get_request(url, params):
      try:
          app_logger(1, "API GET Request", {
            "url": url,
            # "params_keys": list(params.keys()) if isinstance(params, dict) else None,
            "params": params
          })
            
          response = requests.get(url, params=params)  # Make a GET request

          try:
              response_json = response.json()
          except ValueError:
              response_json = {"err_message": response.text}

          # Log response status
          app_logger(1, "API GET Response", {
              "url": url,
              "status_code": response.status_code,
              "response" : response_json,
          })

          if response.status_code in (200, 201):
            return response_json
          else:
            try:
                error_msg = response.json()
            except ValueError:
                error_msg = response.text

            raise Exception(
                f"Failed to fetch data. Status code: {response.status_code}, Message: {error_msg}"
            )

      except requests.RequestException as e:
        app_logger(1, "API GET Error Response", {
          "url": url,
          "err_message": (str(e))
        })
        raise Exception(str(e))
       
      


    @staticmethod
    def post_request(url, payload, headers):

      # Default headers
      default_headers = {
        "Content-Type": "application/json"
      }
        
      # Merge custom headers with defaults (custom headers override defaults)
      if headers:
        merged_headers = {**default_headers, **headers}
      else:
        merged_headers = default_headers
        
      try:
        
        # Log request
        app_logger(1, "API POST Request", {
            "url": url,
            "headers": merged_headers,
            # "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None,
            "payload": payload
        })
            
        response = requests.post(url, json=payload, headers=merged_headers)
        
        try:
            response_json = response.json()
        except ValueError:
            response_json = {"err_message": response.text}

        # Log response status
        app_logger(1, "API POST Response", {
            "url": url,
            "status_code": response.status_code,
            "response" : response_json,
        })
        

        if response.status_code in (200, 201):  # 201 = Created
            
            return response.json()
        
        else:
            
            # try:
            #     error_msg = response.json()
            # except ValueError:
            #     error_msg = response.text
                
            # err_mesasge = f"Failed to post data. Status code: {response.status_code}, Message: {error_msg}"
            err_mesasge = ApiService.extract_error_message(response)

            raise Exception(
                err_mesasge
            )
      except requests.RequestException as e:
          app_logger(1, "API POST Error Exception Response", {
              "url": url,
              "err_message": (str(e))
          })
          raise Exception(str(e))
      

    @staticmethod
    def extract_error_message(response):
        """
        Extract clean error message from API response
        Handles various error response formats
        """
        try:
            error_data = response.json()
            
            # Common error message field names in order of preference
            error_fields = [
                'message',
                'error',
                'err_message', 
                'error_message',
                'detail',
                'msg',
                'responseException'
            ]
            
            # Try to find error message in common fields
            for field in error_fields:
                if field in error_data:
                    # Handle nested responseException (like in TOP.ph API)
                    if field == 'responseException' and isinstance(error_data[field], dict):
                        return error_data[field].get('exceptionMessage', str(error_data[field]))
                    return str(error_data[field])
            
            # If no standard field found, return the whole JSON
            return str(error_data)
            
        except ValueError:
            # If response is not JSON, return text
            return response.text or f"HTTP {response.status_code} Error"