from enum import Enum

__all__ = [
    "ErrorCodes",
]


class ErrorCodes(Enum):
    ACCESS_DENIED = 1
    INVALID_ARGUMENT = 2
    TIMEOUT = 3
    BAD_STATE = 4
    OVERFLOW = 5
    ITEM_NOT_FOUND = 6
