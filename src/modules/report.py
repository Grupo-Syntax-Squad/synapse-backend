from datetime import datetime, timezone
from fastapi import HTTPException, status
from fastapi_mail import (
    FastMail,
    MessageSchema,
    ConnectionConfig,
    MessageType,
)
from pydantic import SecretStr
from sqlalchemy.orm import Session

from src.database.get_db import get_db
from src.database.models import DeliveredTo, Notification, Report, User
from src.enums.notification_type import NotificationType
from src.modules.email_builder import EmailBuilder
from src.settings import settings
from src.schemas.report import SendReport
from src.logger_instance import logger

from typing import Any, List
from sqlalchemy import text
from src.schemas.report import GetReportResponse
from src.schemas.basic_response import BasicResponse
from src.managers.websocket import notifications_manager


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
        self.fm = FastMail(self.conf)

    async def execute(self) -> None:
        logger.info("Iniciando processo de envio de e-mails.")
        await notifications_manager.send_global_message(
            "Initializing send report e-mails process."
        )

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

            users: List[User] = (
                self.session.query(User).filter(User.receive_email.is_(True)).all()
            )
            if not users:
                await notifications_manager.send_global_message(
                    "No user to send report e-mail."
                )
                logger.warning("Nenhum usuário para enviar e-mail.")
                return

            success_count = 0
            failed_users = []

            for user in users:
                failed_user = await self.send_email_to_user(user, report)
                if failed_user:
                    failed_users.append(failed_user)
                else:
                    success_count += 1

            if failed_users:
                await notifications_manager.send_global_message(
                    f"Trying to resend e-mails to {len(failed_users)} with fail."
                )
                final_failed_users = await self.retry_failed_emails(
                    failed_users, report
                )
                success_count += len(users) - len(final_failed_users) - success_count

            logger.info(f"E-mails sended: {success_count}, fails: {len(failed_users)}")
            if failed_users:
                logger.debug(f"Detalhes das falhas: {failed_users}")
                notification = await self.create_email_failure_notification(
                    final_failed_users
                )
                if notification:
                    await notifications_manager.send_notification(
                        notifications_manager.notification_to_schema(notification)
                    )
            else:
                await notifications_manager.send_global_message(
                    "All e-mails sended successfully."
                )
        except Exception as e:
            logger.error(f"Erro ao processar envio de e-mails: {e}")
            await notifications_manager.send_global_message(
                "Error processing e-mails sending."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar envio de e-mails: {e}",
            )

    async def send_email_to_user(self, user: User, report: Report) -> User | None:
        message = MessageSchema(
            subject=report.name,
            recipients=[user.email],
            body=report.content,
            subtype=MessageType.html,
        )
        try:
            await self.fm.send_message(message)
            record = DeliveredTo(report_id=report.id, user_id=user.id)
            self.session.add(record)
            self.session.commit()
            return None
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail para {user.email}: {e}")
            await notifications_manager.send_global_message(
                f"Error sending email to {user.email}"
            )
            self.session.rollback()
            return user

    async def retry_failed_emails(
        self, failed_users: List[User], report: Report, max_retries: int = 3
    ) -> list[User]:
        final_failures: List[User] = failed_users.copy()
        for _ in range(max_retries):
            if not final_failures:
                break
            current_failures = final_failures.copy()
            final_failures = []

            for user_fail in current_failures:
                if not user_fail:
                    continue
                result = await self.send_email_to_user(user_fail, report)
                if result:
                    final_failures.append(result)
        return final_failures

    async def create_email_failure_notification(
        self, failed_users: list[User]
    ) -> Notification | None:
        if not failed_users:
            return None

        failed_emails = [user["email"] for user in failed_users]

        notification = Notification(
            type=NotificationType.FAILED_EMAIL,
            message=f"Fail to send e-mails to {len(failed_emails)} users.",
            details={
                "failed_emails": failed_emails,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        self.session.add(notification)
        self.session.commit()
        self.session.refresh(notification)
        return notification


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


class ReportGenerator:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._log = logger
        self._now = datetime.now(timezone.utc)
        self._report_name = f"Relatório {self._now.strftime('%d/%m/%Y %H:%M')}"

    def execute(self) -> Report:
        try:
            self._log.info("Generating report")
            data = self._get_necessary_processing_data()
            processed_data = self._process_data(data)
            metrics = self._build_metrics(processed_data)
            email = EmailBuilder(self._report_name, self._now, metrics).execute()
            report = self._save_report(email)
            self._log.info("Successfully generated report")
            return report
        except Exception as e:
            self._log.error(f"Error generating report: {e}")
            raise e

    def _get_necessary_processing_data(self) -> dict[str, Any]:
        try:
            queries = {
                "estoque_consumido": """
                    SELECT COALESCE(SUM(es_totalestoque),0) AS total
                    FROM estoque
                    WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                """,
                "frequencia_compra": """
                    SELECT 
                        date_trunc('month', data) AS mes,
                        COUNT(*) AS total_registros
                    FROM faturamento
                    WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                    AND zs_peso_liquido > 0
                    GROUP BY mes
                    ORDER BY mes;
                """,
                "aging": """
                    SELECT AVG(FLOOR(EXTRACT(EPOCH FROM (current_date::timestamp - data)) / (60*60*24*7))) AS idade_media
                    FROM estoque;
                """,
                "clientes_sku1": """
                    SELECT COUNT(DISTINCT cod_cliente) AS clientes
                    FROM faturamento
                    WHERE \"SKU\" = 'SKU_1'
                      AND data BETWEEN current_date - INTERVAL '364 days' AND current_date
                      AND zs_peso_liquido > 0
                """,
                "skus_sem_estoque": """
                    SELECT f.\"SKU\"
                    FROM faturamento f
                    LEFT JOIN estoque e ON e.\"SKU\" = f.\"SKU\"
                    WHERE f.data BETWEEN current_date - INTERVAL '364 days' AND current_date
                    GROUP BY f.\"SKU\", e.es_totalestoque
                    HAVING SUM(f.zs_peso_liquido) > 0 AND COALESCE(SUM(e.es_totalestoque),0) = 0
                """,
                "itens_repor": """
                    WITH consumo_52 AS (
                        SELECT \"SKU\", SUM(zs_peso_liquido) AS total
                        FROM faturamento
                        WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                        GROUP BY \"SKU\"
                    ),
                    estoque_agg AS (
                        SELECT \"SKU\", SUM(es_totalestoque) AS total
                        FROM estoque
                        WHERE data BETWEEN current_date - INTERVAL '364 days' AND current_date
                        GROUP BY \"SKU\"
                    )
                    SELECT c.\"SKU\"
                    FROM consumo_52 c
                    LEFT JOIN estoque_agg e ON e.\"SKU\" = c.\"SKU\"
                    WHERE (c.total/52.0) > 0
                      AND COALESCE(e.total,0) / (c.total/52.0) < 4
                """,
                "risco_sku1": """
                    WITH consumo AS (
                        SELECT SUM(zs_peso_liquido) AS total
                        FROM faturamento
                        WHERE \"SKU\" = 'SKU_1'
                          AND data BETWEEN current_date - INTERVAL '364 days' AND current_date
                    ),
                    est AS (
                        SELECT SUM(es_totalestoque) AS total
                        FROM estoque
                        WHERE \"SKU\" = 'SKU_1'
                    )
                    SELECT 
                        CASE
                            WHEN c.total IS NULL OR c.total = 0 THEN 'Sem histórico'
                            WHEN COALESCE(e.total,0) = 0 THEN 'Alto risco'
                            WHEN COALESCE(e.total,0) / (c.total/52.0) < 2 THEN 'Alto risco'
                            WHEN COALESCE(e.total,0) / (c.total/52.0) < 4 THEN 'Risco médio'
                            ELSE 'Baixo risco'
                        END AS risco
                    FROM consumo c CROSS JOIN est e
                """,
            }

            results: dict[str, Any] = {}
            for key, sql in queries.items():
                res = self._session.execute(text(sql)).fetchall()
                results[key] = [dict(r._mapping) for r in res]

            return results
        except Exception as e:
            self._log.error(f"Error fetching necessary processing data: {str(e)}")
            raise e

    def _process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            processed = {
                "estoque_consumido_ton": float(data["estoque_consumido"][0]["total"]),
                "freq_compra": self._build_frequency(data["frequencia_compra"]),
                "aging_medio": data["aging"][0]["idade_media"],
                "clientes_sku1": data["clientes_sku1"][0]["clientes"],
                "skus_sem_estoque": [row["SKU"] for row in data["skus_sem_estoque"]],
                "itens_repor": [row["SKU"] for row in data["itens_repor"]],
                "risco_sku1": data["risco_sku1"][0]["risco"],
            }
            return processed
        except Exception as e:
            self._log.error(f"Error processing data: {str(e)}")
            raise e

    def _build_metrics(self, processed_data: dict[str, Any]) -> dict[str, str]:
        try:
            metrics = {
                "Estoque consumido (t): ": f"{processed_data['estoque_consumido_ton']:.2f}",
                "Frequência de compra: ": f"<ul>{processed_data['freq_compra']}</ul>",
                "Aging médio (semanas): ": f"{processed_data['aging_medio']:.2f}",
                "Clientes SKU_1: ": str(processed_data["clientes_sku1"]),
                "SKUs sem estoque: ": len(processed_data["skus_sem_estoque"])
                or "Nenhum",
                "Itens a repor: ": len(processed_data["itens_repor"]) or "Nenhum",
                "Risco SKU_1: ": processed_data["risco_sku1"],
            }
            return metrics
        except Exception as e:
            self._log.error(f"Error building report: {str(e)}")
            raise e

    def _build_frequency(self, frequencies_data: list[dict[str, Any]]) -> str:
        frequencies = []
        for data in frequencies_data:
            date = data.get("mes")
            value = data.get("total_registros")
            frequencies.append(
                f"<li style='list-style: none'><strong>{date.strftime('%m/%y')}:</strong> {value}</li>"  # type: ignore[union-attr]
            )
        return "\n".join(frequencies)

    def _save_report(self, content: str) -> Report:
        try:
            report = Report(
                name=self._report_name,
                content=content,
            )
            self._session.add(report)
            self._session.flush()
            self._session.commit()
            return report
        except Exception as e:
            self._log.error(f"Error saving report in database: {str(e)}")
            raise e


class ReportWorkflow:
    def __init__(self) -> None:
        self._session: Session = get_db()
        self._log = logger

    async def execute(self) -> BasicResponse[None]:
        try:
            generated_report = ReportGenerator(self._session).execute()
            send_report = self._build_send_report(generated_report)
            await SendReportToSubscribers(self._session, send_report).execute()
            return BasicResponse(
                message="Report generated and sended to users successfully"
            )
        except HTTPException as e:
            raise e
        except Exception as e:
            self._log.error(f"Error while executing report workflow: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error",
            )

    def _build_send_report(self, report: Report) -> SendReport:
        try:
            return SendReport(subject=report.name, report_id=report.id)
        except Exception as e:
            self._log.error(f"Error creating SendReport: {e}")
            raise e
