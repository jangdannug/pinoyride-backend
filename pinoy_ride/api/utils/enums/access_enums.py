from enum import Enum

class AccessEnum(Enum):
    ALL = "All"
    BENEFICIARY = "Beneficiary"
    VERIFICATION = "Verification"
    CLAIM = "Claim"
    USER = "User"
    PROGRAM="Program"

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

    @classmethod
    def values(cls):
        return [key.value.lower() for key in cls]