from enum import Enum

class BeneficiaryStatusEnum(Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"

    @classmethod
    def choices(cls):
        """Return choices for Django model field"""
        return [(status.value, status.value) for status in cls]

