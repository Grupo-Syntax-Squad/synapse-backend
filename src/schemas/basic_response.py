import json
from pydantic import BaseModel
from typing import Optional, TypeVar, Generic, Union
from fastapi import status
from fastapi.responses import Response
from fastapi.encoders import jsonable_encoder

T = TypeVar("T")


class BasicResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    message: Optional[str] = None