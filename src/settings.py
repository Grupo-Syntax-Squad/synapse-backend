import os
from typing import Any, Callable, Type, TypeVar
from dotenv import load_dotenv

load_dotenv()


T = TypeVar("T")


def singleton(cls: Type[T]) -> Callable[[], T]:
    instances: dict[Type[T], T] = {}

    def get_instance(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


@singleton
class Settings:
    def __init__(self) -> None:
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql://postgres:password@localhost/"
        )
        self.SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
        self.ALGORITHM = os.getenv("ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRATION_TIME_MINUTES", 15)
        )
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(
            os.getenv("REFRESH_TOKEN_EXPIRATION_TIME_DAYS", 7)
        )
        self.NO_AUTH = os.getenv("NO_AUTH", "False").lower() in ("1", "true", "yes")
        if (
            not self.DATABASE_URL
            or not self.SECRET_KEY
        ):
            raise ValueError("Required environment variables are missing!")