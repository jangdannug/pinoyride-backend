from enum import Enum

class AssistanceNeededEnum(Enum):
    MEDICAL = "Medical Assistance"
    FINANCIAL = "Financial Assistance"
    BURIAL = "Burial"
    SOLICITATION = "Solicitation"
    HOSPITAL = "Hospital Bill"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(assistance.value, assistance.value) for assistance in cls]
