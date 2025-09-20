from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from sqlalchemy.orm import Session

from src.database.models import DeliveredTo, Report, User
from src.settings import settings
from src.schemas.report import SendReport
from src.logger_instance import logger


class SendReportToSubscribers:
    def __init__(self, session: Session, request: SendReport):
        self.session = session
        self.request = request
        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=True
        )

    async def execute(self) -> None:
        logger.info("Iniciando processo de envio de e-mails.")
        try:            
            report = self.session.query(Report).filter(Report.id == self.request.report_id).first()
            if not report:
                logger.error(f"Relatório com id {self.request.report_id} não encontrado.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Relatório com id {self.request.report_id} não encontrado."
                )
            
            users = self.session.query(User).filter(User.receive_email == True).all()
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
                    subtype="html"
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

            logger.info(f"E-mails enviados: {success_count}, falhas: {len(failed_users)}")
            logger.debug(f"Detalhes das falhas: {failed_users}")
        

        except Exception as e:
            logger.error(f"Erro ao processar envio de e-mails: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao processar envio de e-mails: {e}"
            )