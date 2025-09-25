from pydantic import BaseModel
from typing import Optional


class GetReportResponse(BaseModel):
    id: int
    name: str
    created_at: str
    content: str
