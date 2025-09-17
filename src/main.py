from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from src.database.get_db import get_db
from src.database.models import Test
from src.modules.root import GetRoot
from src.schemas.basic_response import BasicResponse

app = FastAPI()


@app.get("/")
def read_root() -> BasicResponse[None]:
    return GetRoot().execute()


@app.post("/test")
def create_test(name: str, session: Session = Depends(get_db)) -> BasicResponse[None]:
    new_test = Test(**{"name": name})
    session.add(new_test)
    session.commit()
    return BasicResponse(message="Entidade de teste criada com sucesso")


Instrumentator().instrument(app).expose(app)
