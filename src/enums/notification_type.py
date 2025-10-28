from enum import Enum


class NotificationType(str, Enum):
    GENERIC = "generic"
    FAILED_EMAIL = "failed_email"
    NEW_USER = "new_user"
