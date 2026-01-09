from django.db import transaction
from api.repositories import PromoRepository, PromoAvailedRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from django.utils import timezone
class PromoService:
    
    def __init__(self):
        self.promo = PromoRepository()
        self.promo_availed = PromoAvailedRepository()

    ## Get promo by id
    def get_promo_by_id(self,promo_id):
        """Fetch promo"""
        promo = self.promo.get_by_id(promo_id=promo_id)
        
        if promo is None:
            raise NotFoundError("Promo "+ str(promo_id) + " not found")
        return promo
    
     ## Get promo by code
    def get_promo_by_code(self,promo_code, customer_id):
        """Fetch promo by code"""
        promo = self.promo.get_by_code(promo_code=promo_code)
        
        if promo is None:
            raise NotFoundError("Promo "+ str(promo_code) + " not found")
        
        # validate promo
        PromoService.validate_promo(self, promo_id=promo.id, customer_id=customer_id)

        return promo
    

    ## list of promos
    def get_promo_list(self, customer_id):
        """List all promos with pagination"""
        return self.promo.promo_list(customer_id)
    

    ## Validate Promo
    def validate_promo(self,promo_id, customer_id):
        """Validate promo """
        promo = self.promo.get_by_id(promo_id=promo_id)
        
        if promo is None:
            raise NotFoundError("Promo not found")
        
        now = timezone.localdate()
        
        if promo:
            if promo.status == 0:
                raise NotFoundError("Promo "+ str(promo.code) + " not found")
            
            # Check start date
            if promo.start_date and promo.start_date > now:
                raise ValidationError("This promo code has not started yet.")

            # Check expiry date
            if promo.end_date and promo.end_date < now:
                raise ValidationError(f"This promo code has expired. Please try another promo.")
            
            #Check if promo is alraedy availed
            is_availed = self.promo_availed.check_if_availed(promo_id=promo_id, customer_id=customer_id)
            if is_availed:
                raise ValidationError(f"You already availed this promo.")

            ## Check if limit reached
            count_promo_availed = self.promo_availed.count_promo_availed(promo_id=promo_id)
            if promo.no_of_users is not None and count_promo_availed >= promo.no_of_users:
                raise ValidationError("Promo usage limit reached.")
            
        return True