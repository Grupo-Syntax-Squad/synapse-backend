from typing import Any
from sqlalchemy.orm import Mapped, mapped_column, declarative_base, relationship
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy import Enum as SQLEnum
from datetime import datetime

from src.enums.notification_type import NotificationType

Base = declarative_base()


class Example(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "example"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_onupdate=func.now())


class User(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    password: Mapped[str] = mapped_column(String)
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    receive_email: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
    last_update: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_access: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType), nullable=False
    )
    message: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    visualized: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
    visualizedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    visualizedBy: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True
    )


class Report(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content: Mapped[str] = mapped_column(String, nullable=False)

    delivered_to: Mapped[list["DeliveredTo"]] = relationship(
        "DeliveredTo", back_populates="report", cascade="all, delete-orphan"
    )


class DeliveredTo(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "delivered_to"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("report.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)

    report: Mapped["Report"] = relationship("Report", back_populates="delivered_to")
    user: Mapped["User"] = relationship("User")


class Test(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)


class Clients(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "clientes"

    cod_cliente: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str | None] = mapped_column(String(100))


class Estoque(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "estoque"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[datetime] = mapped_column(DateTime)
    cod_cliente: Mapped[int] = mapped_column(ForeignKey("clientes.cod_cliente"))
    es_centro: Mapped[str] = mapped_column(String(50))
    tipo_material: Mapped[str] = mapped_column(String(100))
    origem: Mapped[str] = mapped_column(String(50))
    cod_produto: Mapped[str] = mapped_column(String(50))
    lote: Mapped[str] = mapped_column(String(50))
    dias_em_estoque: Mapped[int] = mapped_column(Integer)
    produto: Mapped[str] = mapped_column(String(100))
    grupo_mercadoria: Mapped[str] = mapped_column(String(100))
    es_totalestoque: Mapped[float] = mapped_column(Numeric)
    sku: Mapped[str] = mapped_column(String(50))


class Faturamento(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "faturamento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[datetime] = mapped_column(DateTime)
    cod_cliente: Mapped[int] = mapped_column(ForeignKey("clientes.cod_cliente"))
    lote: Mapped[str] = mapped_column(String(50))
    origem: Mapped[str] = mapped_column(String(50))
    zs_gr_mercad: Mapped[str] = mapped_column(String(100))
    produto: Mapped[str] = mapped_column(String(100))
    cod_produto: Mapped[str] = mapped_column(String(50))
    zs_centro: Mapped[str] = mapped_column(String(50))
    zs_cidade: Mapped[str] = mapped_column(String(100))
    zs_uf: Mapped[str] = mapped_column(String(10))
    zs_peso_liquido: Mapped[float] = mapped_column(Numeric)
    giro_sku_cliente: Mapped[float] = mapped_column(Numeric)
    sku: Mapped[str] = mapped_column(String(50))


class ChatHistory(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(String)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user_message: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime)
