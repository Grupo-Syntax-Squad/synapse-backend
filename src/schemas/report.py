from pydantic import BaseModel
from typing import Optional


class SendReport(BaseModel):
    report_id: int
    subject: str


class GetReportResponse(BaseModel):
    id: int
    name: str
    created_at: str
    content: str
