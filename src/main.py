from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from src.database.get_db import engine, get_db
from src.database.models import Base, Test
from src.logger_instance import logger
from src.modules.data_loader import DataLoader
from src.modules.report_scheduler import (
    scheduler,
    start_scheduler,
)
from src.modules.root import GetRoot
from src.routers import auth, chat, notification, report, user, websocket
from src.schemas.basic_response import BasicResponse
from src.settings import settings

logger.debug(f"System settings: {settings}")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        DataLoader(session).execute()
    if not settings.TESTING:
        start_scheduler()
    yield
    if not settings.TESTING:
        scheduler.shutdown()


app = FastAPI(title="Synapse Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(report.router)
app.include_router(websocket.router)
app.include_router(notification.router)
app.include_router(chat.router)


@app.get("/")
def read_root() -> BasicResponse[None]:
    return GetRoot().execute()


@app.post("/test")
def create_test(name: str, session: Session = Depends(get_db)) -> BasicResponse[None]:
    new_test = Test(name=name)
    session.add(new_test)
    session.commit()
    return BasicResponse(message="Entidade de teste criada com sucesso")


Instrumentator().instrument(app).expose(app)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
