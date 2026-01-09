from django.db import transaction
from api.repositories import PromoAvailedRepository
from api.utils.custom_error import NotFoundError,ValidationError
from api.utils.auth import get_authenticated_user
from api.utils.sha_generator import generate_sha512
import base64
class PromoAvailedService:
    
    def __init__(self):
        self.promo_availed = PromoAvailedRepository()
    
    ## Save promo avaied
    @transaction.atomic
    def save_promo_availed(self, promo_instance, customer_instance, booking_instance):
        """Save promo availed"""
        
        new_promo_availed = self.promo_availed.create(promo_instance = promo_instance, customer_instance=customer_instance, booking_instance=booking_instance)

        return new_promo_availed


    ## Get promo availed by booking id
    @transaction.atomic
    def get_promo_availed_by_booking_id(self,booking_id):
        """Fetch promo"""
        promo_availed = self.promo_availed.get_by_booking_id(booking_id=booking_id)
        
        if promo_availed is None:
            return None
        return promo_availed
    

    ## Update promo availed status
    @transaction.atomic
    def update_promo_availed_status(self, promo_availed_instance, status):
        """Update promo availed status"""
        
        promo_avail_status = self.promo_availed.update_promo_availed_status(promo_availed_instance=promo_availed_instance, status=status)

        return promo_avail_status