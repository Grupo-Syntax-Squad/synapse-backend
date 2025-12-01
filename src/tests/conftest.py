from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.get_db import get_db
from src.database.models import Base, Report
from src.main import app
from src.modules.report_scheduler import scheduler
from src.nlp.intent_classifier import RuleIntentClassifier
from src.settings import settings


@pytest.fixture
def report_data(session: Session) -> list[Report]:
    reports = [
        Report(
            name="Relatório 1",
            created_at=datetime.now() - timedelta(days=2),
            content="Conteúdo do relatório 1",
        ),
        Report(
            name="Relatório 2",
            created_at=datetime.now() - timedelta(days=1),
            content="Conteúdo do relatório 2",
        ),
    ]
    session.add_all(reports)
    session.commit()
    return reports


@pytest.fixture(autouse=True)
def disable_loki_logging() -> Generator[None, None, None]:
    with patch("logging_loki.handlers.LokiHandler.emit"):
        yield


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: session
    # impede que o scheduler seja iniciado/desligado durante os testes
    with (
        patch("src.modules.report_scheduler.scheduler.start"),
        patch("src.modules.report_scheduler.start_scheduler"),
        patch("src.modules.report_scheduler.scheduler.shutdown"),
    ):
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


@pytest.fixture(autouse=True)
def disable_scheduler() -> Generator[None, None, None]:
    with patch.object(scheduler, "start", lambda *a, **kw: None):
        yield


@pytest.fixture
def classifier() -> RuleIntentClassifier:
    return RuleIntentClassifier()
