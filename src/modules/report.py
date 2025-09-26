from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import SecretStr
from sqlalchemy.orm import Session

from src.database.models import DeliveredTo, Report, User
from src.settings import settings
from src.schemas.report import SendReport
from src.logger_instance import logger

from typing import Any
from sqlalchemy import text
from src.schemas.report import GetReportResponse
from src.schemas.basic_response import BasicResponse


class SendReportToSubscribers:
    def __init__(self, session: Session, request: SendReport):
        self.session = session
        self.request = request
        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=True,
        )

    async def execute(self) -> None:
        logger.info("Iniciando processo de envio de e-mails.")
        try:
            report = (
                self.session.query(Report)
                .filter(Report.id == self.request.report_id)
                .first()
            )
            if not report:
                logger.error(
                    f"Relatório com id {self.request.report_id} não encontrado."
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Relatório com id {self.request.report_id} não encontrado.",
                )

            users = self.session.query(User).filter(User.receive_email.is_(True)).all()
            if not users:
                logger.warning("Nenhum usuário para enviar e-mail.")
                return

            fm = FastMail(self.conf)
            success_count = 0
            failed_users = []

            for user in users:
                message = MessageSchema(
                    subject=self.request.subject,
                    recipients=[user.email],
                    body=report.content,
                    subtype=MessageType.html,
                )
                try:
                    await fm.send_message(message)

                    record = DeliveredTo(report_id=None, user_id=user.id)
                    self.session.add(record)
                    self.session.commit()
                    success_count += 1

                except Exception as e:
                    logger.error(f"Erro ao enviar e-mail para {user.email}: {e}")
                    self.session.rollback()
                    failed_users.append({"email": user.email, "error": str(e)})

            logger.info(
                f"E-mails enviados: {success_count}, falhas: {len(failed_users)}"
            )
            logger.debug(f"Detalhes das falhas: {failed_users}")

        except Exception as e:
            logger.error(f"Erro ao processar envio de e-mails: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar envio de e-mails: {e}",
            )


class GetReports:
    def __init__(self, session: Session, filters: dict[str, Any]):
        self._session = session
        self._filters = filters

    def execute(self) -> BasicResponse[list[GetReportResponse]]:
        self._get_reports()
        response = self._format_response()
        return BasicResponse(data=response)

    def _get_reports(self) -> None:
        base_query = "SELECT * FROM report WHERE 1=1"
        params: dict[str, Any] = {}

        if self._filters:
            if self._filters.get("start_date"):
                base_query += " AND created_at >= :start_date"
                params["start_date"] = self._filters.get("start_date")
            if self._filters.get("end_date"):
                base_query += " AND created_at <= :end_date"
                params["end_date"] = self._filters.get("end_date")

        with self._session as session:
            query = text(base_query).bindparams(**params)
            result = session.execute(query)
            reports = result.fetchall()
            self.result: list[dict[str, Any]] = [report._asdict() for report in reports]

    def _format_response(self) -> list[GetReportResponse]:
        return [
            GetReportResponse(
                id=result["id"],
                name=result["name"],
                created_at=result["created_at"].isoformat(),
                content=result["content"],
            )
            for result in self.result
        ]


class GetReportById:
    def __init__(self, session: Session, report_id: int):
        self._session = session
        self._report_id = report_id

    def execute(self) -> BasicResponse[GetReportResponse | None]:
        self._get_report()
        if not self.result:
            return BasicResponse(data=None, message="Report not found")
        response = self._format_response()
        return BasicResponse(data=response)

    def _get_report(self) -> None:
        with self._session as session:
            query = text("""SELECT * FROM report WHERE id=:id""").bindparams(
                id=self._report_id
            )
            result = session.execute(query).fetchone()
            self.result: dict[str, Any] | None = result._asdict() if result else None

    def _format_response(self) -> GetReportResponse | None:
        response = (
            GetReportResponse(
                id=self.result["id"],
                name=self.result["name"],
                created_at=self.result["created_at"].isoformat(),
                content=self.result["content"],
            )
            if self.result
            else None
        )
        return response
