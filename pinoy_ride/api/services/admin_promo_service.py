from django.db import transaction
from api.repositories import PromoRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
class AdminPromoService:
    
    def __init__(self):
        self.promo = PromoRepository()

    
    ## Create promo
    @transaction.atomic
    def create_promo(self, promo, auth_user_id):
        """Creates promo"""
        
        new_promo = self.promo.create(promo, auth_user_id)

        return new_promo


    ## Get promo by id
    def get_promo_by_id(self,promo_id):
        """Fetch promo"""
        promo = self.promo.get_by_id(promo_id=promo_id)
        
        if promo is None:
            raise NotFoundError("Promo "+ str(promo_id) + " not found")
        return promo

    ## Update promo
    @transaction.atomic
    def update_promo(self, promo, update_data):
        """Update promo"""

        update_promo = self.promo.update_promo(promo_instance=promo, update_data=update_data)
    
        return update_promo


    ## Update promo status
    @transaction.atomic
    def update_promo_status(self, promo, promo_status):
        """Update promo status"""

        update_promo = self.promo.update_promo_status(promo_instance=promo, promo_status=promo_status)
    
        return update_promo


    ## Admin get list of promos
    def admin_list_promos(self, page_number=1, page_size=10, search_query=None, filters={}, sort_by="-updated_at"):
        """List all promos with pagination"""
        return self.promo.admin_promo_list(page_number, page_size, search_query, filters, sort_by)