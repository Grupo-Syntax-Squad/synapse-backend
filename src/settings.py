from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TESTING: bool = Field(default=False, env=["TESTING"])  # type: ignore
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRATION_TIME_MINUTES: int
    REFRESH_TOKEN_EXPIRATION_TIME_DAYS: int
    NO_AUTH: bool
    LOKI_ENDPOINT: str
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    HOST: str
    PORT: int
    EMAIL_TEMPLATE_PATH: str
    GITHUB_URL: str
    SCHEDULED_REPORT_GENERATION_MINUTES: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
