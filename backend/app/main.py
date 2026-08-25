from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import crud
from app.config import settings
from app.db import SessionLocal
from app.routers import environments, health, slots


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = SessionLocal()
    try:
        crud.ensure_default_slots(db, settings.num_save_slots)
    finally:
        db.close()
    yield


app = FastAPI(title="Background Evolution API", lifespan=lifespan)

app.include_router(health.router)
app.include_router(slots.router)
app.include_router(environments.router)
