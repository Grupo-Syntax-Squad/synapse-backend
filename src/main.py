from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.modules.root import GetRoot
from src.schemas.basic_response import BasicResponse

app = FastAPI()


@app.get("/")
def read_root() -> BasicResponse[None]:
    return GetRoot().execute()


Instrumentator().instrument(app).expose(app)
