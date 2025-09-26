from pydantic import BaseModel


class GetReportResponse(BaseModel):
    id: int
    name: str
    created_at: str
    content: str
