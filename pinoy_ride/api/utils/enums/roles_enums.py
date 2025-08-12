
from enum import Enum

class RolesEnum(Enum):
    SUPERVISOR = "Supervisor"
    ADMIN = "Admin"
    ENCODER = "Encoder"

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

    @classmethod
    def values(cls):
        return [key.value for key in cls]