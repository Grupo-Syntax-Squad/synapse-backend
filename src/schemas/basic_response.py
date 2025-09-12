from pydantic import BaseModel
from typing import Optional, TypeVar, Generic

T = TypeVar("T")


class BasicResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    message: Optional[str] = "OK"
