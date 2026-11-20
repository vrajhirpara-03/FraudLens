from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.app.services.model import ModelService
from backend.app.api.predictions import router as prediction_router
from backend.app.api.statements import router as statement_router
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.health import router as health_router
from backend.app.core.config import settings

@asynccontextmanager
async def lifespan(app):
    app.state.model = ModelService()
    app.state.model.load()
    yield


app = FastAPI(lifespan=lifespan, title="FraudLens API", version="0.1.0", description="Credit card fraud detection research prototype.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router, prefix="/api")

app.include_router(prediction_router, prefix="/api")
app.include_router(statement_router, prefix="/api")
