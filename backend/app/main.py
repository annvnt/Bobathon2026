"""EcoComply FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import SessionLocal, init_db
from .routers import alerts, meta, products
from .scheduler import shutdown_scheduler, start_scheduler
from .seed import seed_from_partners
from .services.llm import LLMError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ecocomply")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_from_partners(db)
    finally:
        db.close()
    start_scheduler()
    logger.info("EcoComply backend ready (LLM=%s, alerts=%s)",
                settings.LLM_PROVIDER, settings.ALERTS_PROVIDER)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="EcoComply API",
    description="AI regulatory compliance platform for electronics SMEs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(alerts.router)
app.include_router(meta.router)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": f"LLM unavailable: {exc}"},
    )


@app.get("/")
def root() -> dict:
    return {"name": "EcoComply API", "docs": "/docs"}
