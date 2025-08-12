from enum import Enum

class TypeOfAssistanceEnum(Enum):
    MEDICAL = "Medical Assistance"
    FINANCIAL = "Financial Assistance"
    BURIAL = "Burial"
    SOLICITATION = "Solicitation"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(assistance.value, assistance.value) for assistance in cls]
