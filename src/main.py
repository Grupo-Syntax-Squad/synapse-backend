from fastapi import FastAPI

from src.database.models import Base
from src.database.get_db import engine
from src.routers import auth, user

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(user.router)

