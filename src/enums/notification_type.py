from enum import Enum

class NotificationType(str, Enum):
    FAILED_EMAIL = "failed_email"
    NEW_USER = "new_user"