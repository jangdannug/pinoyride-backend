from rest_framework import serializers
from api.models import TopPhEkycDetails

class TopPhEkycDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = TopPhEkycDetails
        fields = [
            "id",
            "generate_request_user_id",
            "kyc_id",     
            "first_name",              
            "middle_name",           
            "last_name",
            "email_address",     
            "mobile_no",            
            "date_of_birth",        
            "place_of_birth",        
            "nationality",         
            "gender",             
            "current_country",      
            "current_address",      
            "nature_of_work",       
            "source_of_fund",        
            "id_type",             
            "id_number",             
            "id_front",               
            "id_back",                
            "selfie",                
            "status",
            "pretty_mobile_no",
            "permanent_address",   
            "permanent_country",   
        ]
    