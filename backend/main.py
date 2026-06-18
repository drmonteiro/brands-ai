"""
FastAPI Backend for Confeções Lança Lead Generation
"""
import logging
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.database import init_database
from services.postgres import PostgresManager
from routers import prospects, cities, analytics, workflow, email, export, chat, whatsapp

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_FORMAT = "%(asctime)s │ %(levelname)-7s │ %(name)-22s │ %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    stream=sys.stdout,
    force=True,
)
# Silence noisy third-party loggers
for noisy in ("httpx", "httpcore", "urllib3", "openai", "exa_py", "asyncio", "psycopg_pool", "psycopg"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger("api")


def _cors_origins() -> list:
    """Allow explicit deploy URLs via CORS_ORIGINS (comma-separated) plus defaults."""
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Next.js dev fallback when port 3000 is taken
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://ambitious-coast-0f9176703.1.azurestaticapps.net",
    ]
    extra = os.getenv("CORS_ORIGINS", "")
    if extra.strip():
        for o in extra.split(","):
            u = o.strip()
            if u and u not in defaults:
                defaults.append(u)
    return defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_database()
        logger.info("PostgreSQL database initialized")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
    yield
    await PostgresManager.close()
    logger.info("PostgreSQL connection pool closed")

app = FastAPI(
    title="Confeções Lança Lead Generation API",
    version="1.1.0",
    lifespan=lifespan,
)

_origins = _cors_origins()
logger.info("CORS allow_origins: %s", _origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(workflow.router)
app.include_router(prospects.router)
app.include_router(cities.router)
app.include_router(analytics.router)
app.include_router(email.router)
app.include_router(export.router)
app.include_router(chat.router)
app.include_router(whatsapp.router)

@app.get("/")
async def root():
    return {"status": "healthy", "version": "1.1.0"}
