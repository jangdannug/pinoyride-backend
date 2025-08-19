from django.db import transaction
from api.repositories import CustomerRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
import requests

class ApiService:
    
    def __init__(self):
        self.customer = CustomerRepository()
    

    @staticmethod
    def get_request(url, params):
      try:
          response = requests.get(url, params=params)  # Make a GET request

          if response.status_code in (200, 201):
            data = response.json()  # Convert JSON response to a Python dictionary
            return data
          else:
            try:
                error_msg = response.json()
            except ValueError:
                error_msg = response.text

            raise Exception(
                f"Failed to fetch data. Status code: {response.status_code}, Message: {error_msg}"
            )

      except requests.RequestException as e:
        raise Exception(str(e))
       
      
    @staticmethod
    def post_request(url, payload):

      headers = {"Content-Type": "application/json"}  # Tell API we’re sending JSON

      try:
          response = requests.post(url, json=[], headers=headers)

          if response.status_code in (200, 201):  # 201 = Created
              return response.json()
          else:

            try:
                error_msg = response.json()
            except ValueError:
                error_msg = response.text

            raise Exception(
                f"Failed to post data. Status code: {response.status_code}, Message: {error_msg}"
            )

      except requests.RequestException as e:
          raise Exception(str(e))