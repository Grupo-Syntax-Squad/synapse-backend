from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uvicorn
from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from src.settings import settings
from src.database.get_db import get_db
from src.database.models import Test
from src.modules.root import GetRoot
from src.schemas.basic_response import BasicResponse
from src.routers import auth, user, report
from src.modules.report_scheduler import (
    scheduler,
    start_scheduler,
)

origins = [
    "http://localhost:5173/",
    "http://127.0.0.1:5173/",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler.start()
    start_scheduler()
    yield
    scheduler.shutdown()


app = FastAPI(title="Synapse Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[""],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(report.router)


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
