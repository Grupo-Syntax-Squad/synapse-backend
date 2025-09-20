from sqlalchemy.orm import Mapped, mapped_column, declarative_base, relationship
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from datetime import datetime

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


class Report(Base):   # type: ignore[valid-type, misc]
    __tablename__ = "report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    content: Mapped[str] = mapped_column(String, nullable=False)

    delivered_to: Mapped[list["DeliveredTo"]] = relationship(
        "DeliveredTo",
        back_populates="report",
        cascade="all, delete-orphan"
    )


class DeliveredTo(Base):   # type: ignore[valid-type, misc]
    __tablename__ = "delivered_to"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("report.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)

    report: Mapped["Report"] = relationship("Report", back_populates="delivered_to")
    user: Mapped["User"] = relationship("User")


class Test(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
