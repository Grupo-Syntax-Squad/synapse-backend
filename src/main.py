from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.schemas.basic_response import BasicResponse

from src.database.models import Base
from src.database.get_db import engine
from src.routers import auth, user

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(user.router)


@app.get("/")
def read_root() -> BasicResponse[None]:
    return BasicResponse(message="Hello World!")


Instrumentator().instrument(app).expose(app)
