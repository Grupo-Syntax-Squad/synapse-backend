from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.schemas.basic_response import BasicResponse

app = FastAPI()


@app.get("/")
def read_root() -> BasicResponse[None]:
    return BasicResponse(message="Hello World!")


Instrumentator().instrument(app).expose(app)
