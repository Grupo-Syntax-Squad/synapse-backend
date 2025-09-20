import uvicorn
from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from src.settings import settings
from src.database.get_db import get_db
from src.database.models import Test
from src.modules.root import GetRoot
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
    return GetRoot().execute()


@app.post("/test")
def create_test(name: str, session: Session = Depends(get_db)) -> BasicResponse[None]:
    new_test = Test(**{"name": name})
    session.add(new_test)
    session.commit()
    return BasicResponse(message="Entidade de teste criada com sucesso")


Instrumentator().instrument(app).expose(app)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
