import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import patch

from src.main import app
from src.settings import settings
from src.database.models import Base
from src.database.get_db import get_db


@pytest.fixture(autouse=True)
def disable_loki_logging() -> Generator[None, None, None]:
    with patch("logging_loki.handlers.LokiHandler.emit"):
        yield


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def engine() -> Engine:
    return create_engine(settings.DATABASE_URL)


@pytest.fixture(scope="session")
def tables(engine) -> Generator[None, None, None]:  # type: ignore[no-untyped-def]
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables) -> Generator[Session, None, None]:  # type: ignore[no-untyped-def]
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
