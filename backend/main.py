"""
FastAPI Backend for Confeções Lança Lead Generation
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.database import init_database
from services.postgres import PostgresManager
from routers import prospects, cities, analytics, workflow, email

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    try:
        await init_database()
        print("[API] ✅ PostgreSQL database initialized")
    except Exception as e:
        print(f"[API] ❌ Database initialization failed: {e}")
    yield
    # Shutdown
    await PostgresManager.close()
    print("[API] 🛑 PostgreSQL connection pool closed")

app = FastAPI(
    title="Confeções Lança Lead Generation API",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/")
async def root():
    return {"status": "healthy", "version": "1.1.0"}
