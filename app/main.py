# app/main.py
import logging
import time
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import catalog_engine
from app.core.cache import cache
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.kafka.producer import start_producer, stop_producer
    logger.info("Admin Service starting...")
    await start_producer()
    yield
    await stop_producer()
    logger.info("Admin Service shutting down")


app = FastAPI(
    title="Admin Service",
    description="Gestión de películas, teatros, usuarios y reportes (solo admin)",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    logger.info("[%s] %s %s", request_id, request.method, request.url.path)
    response = await call_next(request)
    logger.info(
        "[%s] %s | %.2fs", request_id, response.status_code, time.time() - start
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router)


@app.get("/health", tags=["Health"])
async def health_check():
    try:
        with Session(catalog_engine) as db:
            db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as err:
        logger.error("DB health check failed: %s", err)
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": settings.VERSION,
        "database": db_status,
        "cache": "connected" if cache.is_healthy() else "unavailable",
    }
