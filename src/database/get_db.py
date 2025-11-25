from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.settings import settings


engine = create_engine(settings.DATABASE_URL, echo=False)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionFactory()
    return db
