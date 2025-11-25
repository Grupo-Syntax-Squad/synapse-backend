import secrets
import redis
from datetime import datetime, timezone
from jinja2 import Template
from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from src.logger_instance import logger
from src.settings import settings
from src.database.models import User
from src.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest
from src.auth.auth_utils import Auth


class ResetPasswordEmailBuilder:
    def __init__(self, code: str, username: str):
        self._code = code
        self._username = username
        self._template_path = settings.RESET_TEMPLATE_PATH
        self._log = logger

    def execute(self) -> str:
        try:
            with open(self._template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            template = Template(template_content)
            return template.render(
                subject="Recuperação de Senha",
                username=self._username,
                code=self._code,
                current_year=datetime.now(timezone.utc).strftime("%Y"),
            )
        except Exception as e:
            self._log.error(f"Erro ao construir e-mail de reset: {e}")
            raise


class SendResetEmailService:
    def __init__(self, user: User, code: str):
        self._user = user
        self._code = code
        self._log = logger
        self._conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            # settings.MAIL_PASSWORD is a pydantic SecretStr; ConnectionConfig
            # expects a SecretStr for MAIL_PASSWORD, so pass it directly.
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=settings.MAIL_STARTTLS,
            MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
            USE_CREDENTIALS=True,
        )

    async def execute(self) -> None:
        try:
            builder = ResetPasswordEmailBuilder(
                code=self._code, username=self._user.username
            )
            html_body = builder.execute()

            message = MessageSchema(
                subject="Instruções para Recuperação de Senha",
                recipients=[self._user.email],
                body=html_body,
                subtype=MessageType.html,
            )

            fm = FastMail(self._conf)
            await fm.send_message(message)
            self._log.info(f"E-mail de reset enviado para {self._user.email}")

        except Exception as e:
            self._log.error(
                f"Falha ao enviar e-mail de reset para {self._user.email}: {e}"
            )


class RequestPasswordResetService:
    def __init__(
        self,
        session: Session,
        redis_client: redis.Redis,
        request: ForgotPasswordRequest,
    ):
        self._session = session
        self._redis = redis_client
        self._request = request
        self._log = logger

    def execute(self) -> tuple[User, str] | None:
        try:
            self._log.info(f"Iniciando solicitação de reset para {self._request.email}")
            user = self._session.execute(
                select(User).where(User.email == self._request.email)
            ).scalar_one_or_none()

            if user is None:
                self._log.warning(
                    f"Tentativa de reset para email não existente: {self._request.email}"
                )
                return None
            code = "".join(str(secrets.randbelow(10)) for _ in range(6))
            key = f"reset_code:{user.email}"
            ttl_seconds = 900
            self._redis.setex(name=key, time=ttl_seconds, value=code)
            self._log.debug(f"Token de reset gerado no Redis para o usuário {user.id}")
            return user, code
        except redis.RedisError as e:
            self._log.error(f"Erro do Redis ao gerar token: {e}")
            return None
        except Exception as e:
            self._log.error(f"Erro ao gerar token de reset: {e}")
            return None


class ResetPasswordService:
    def __init__(
        self, session: Session, redis_client: redis.Redis, request: ResetPasswordRequest
    ):
        self._session = session
        self._redis = redis_client
        self._request = request
        self._log = logger

    def execute(self) -> None:
        try:
            self._log.info("Tentando resetar a senha via token do Redis")
            key = f"reset_code:{self._request.email}"
            stored_code = self._redis.get(key)
            if stored_code is None:
                self._log.warning("Código expirado ou inexistente")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Código expirado ou inválido",
                )
            if stored_code != self._request.code:
                self._log.warning(
                    f"Código incorreto fornecido para {self._request.email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Código incorreto",
                )
            user = self._session.execute(
                select(User).where(User.email == self._request.email)
            ).scalar_one_or_none()
            if user is None:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")

            hashed = Auth.get_password_hash(self._request.new_password)
            user.password = hashed
            user.last_update = datetime.now(timezone.utc)
            self._session.commit()
            self._redis.delete(key)
            self._log.info(f"Senha do usuário {user.id} alterada com sucesso via token")

        except HTTPException:
            self._session.rollback()
            raise
        except redis.RedisError as e:
            self._session.rollback()
            self._log.error(f"Erro do Redis ao resetar senha: {e}")
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            self._session.rollback()
            self._log.error(f"Erro ao resetar senha: {e}")
            raise HTTPException(
                detail="Internal error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
