from django.db import transaction
from api.repositories import PriceRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
class AdminPriceService:
    
    def __init__(self):
        self.price = PriceRepository()

    
    ## Create price
    @transaction.atomic
    def create_price(self, price, auth_user_id):
        """Creates price"""
        
        new_price = self.price.create(price, auth_user_id)

        return new_price


    ## Get price by id
    def get_price_by_id(self,price_id):
        """Fetch price"""
        price = self.price.get_by_id(price_id=price_id)

        if price is None:
            raise NotFoundError("Price "+ str(price_id) + " not found")
        return price


    ## Get latest price
    def get_latest_price(self):
        """Fetch the latest active price"""
        price = self.price.get_latest_price()

        if price is None:
            return None
        return price

    ## Update price
    @transaction.atomic
    def update_price(self, price, update_data):
        """Update price"""

        update_price = self.price.update_price(price_instance=price, update_data=update_data)
    
        return update_price


    ## Update price status
    @transaction.atomic
    def update_price_status(self, price, price_status):
        """Update price status"""

        update_price = self.price.update_price_status(price_instance=price, price_status=price_status)
    
        return update_price


    ## Admin get list of prices
    def admin_list_price(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all prices with pagination"""
        return self.price.admin_price_list(page_number, page_size, search_query, filters, sort_by)