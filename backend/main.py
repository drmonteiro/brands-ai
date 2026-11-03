"""
FastAPI Backend for Confeções Lança Lead Generation
"""
import asyncio
import logging
import os
import sys
import time
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.auth import require_user
from services.database import init_database
from services.postgres import PostgresManager

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
request_logger = logging.getLogger("api.requests")

SLOW_REQUEST_MS = 3000
_process_started = time.monotonic()


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


async def _init_database_background() -> None:
    """Run migrations without blocking HTTP startup (Azure cold start)."""
    try:
        await init_database()
        logger.info("PostgreSQL database initialized")
    except Exception as e:
        logger.error("Database initialization failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_task = asyncio.create_task(_init_database_background())
    yield
    init_task.cancel()
    try:
        await init_task
    except asyncio.CancelledError:
        pass
    await PostgresManager.close()
    logger.info("PostgreSQL connection pool closed")

app = FastAPI(
    title="Confeções Lança Lead Generation API",
    version="1.1.0",
    lifespan=lifespan,
    # The schema would list every route to anyone. Nothing in the app uses these.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    """Uptime separates a slow request on a fresh container from one on a settled container."""
    started = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - started) * 1000
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.0f}"
    request_logger.log(
        logging.WARNING if duration_ms >= SLOW_REQUEST_MS else logging.INFO,
        "%s %s %s status=%d duration_ms=%.0f uptime_s=%.0f",
        "SLOW_REQUEST" if duration_ms >= SLOW_REQUEST_MS else "REQUEST",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        time.monotonic() - _process_started,
    )
    return response


# Core routers — lightweight imports for fast cold start
from routers import prospects, cities, analytics, workflow, email, export, linkedin

_requires_user = [Depends(require_user)]

for _router in (workflow, prospects, cities, analytics, email, linkedin, export):
    app.include_router(_router.router, dependencies=_requires_user)

# Heavy routers (LangChain, Twilio) — optional; core API must start even if these fail
def _register_heavy_routers() -> None:
    try:
        from routers import chat, whatsapp
        app.include_router(chat.router, dependencies=_requires_user)
        # Twilio can't send a user token: the webhook checks Twilio's signature itself.
        app.include_router(whatsapp.router)
        logger.info("Chat/WhatsApp routers registered")
    except Exception as e:
        logger.error("Chat/WhatsApp routers disabled: %s", e)

_register_heavy_routers()

@app.get("/")
async def root():
    return {"status": "healthy", "version": "1.1.0"}


@app.get("/health")
async def health():
    """Lightweight probe — no DB, for Azure / load balancers."""
    return {"status": "ok"}
