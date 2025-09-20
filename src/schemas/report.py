from pydantic import BaseModel


class SendReport(BaseModel):
    report_id: int
    subject: str