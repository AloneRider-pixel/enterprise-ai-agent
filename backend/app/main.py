"""
FastAPI application entry point.
Configures middleware, routes, and lifecycle events.
"""
import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_database, vector_store
from app.redis_client import redis_client

# ─── Configure Structured Logging ───

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = logging.getLogger(__name__)


# ─── Lifespan Events ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # ─── Startup ───
    logger.info("Starting Enterprise AI Agent...")
    
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    
    # Connect Redis
    try:
        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    
    # Connect pgvector store
    try:
        await vector_store.connect()
        logger.info("pgvector store connected")
    except Exception as e:
        logger.error(f"pgvector connection failed: {e}")
    
    logger.info("Enterprise AI Agent ready ✓")
    
    yield
    
    # ─── Shutdown ───
    logger.info("Shutting down...")
    await vector_store.disconnect()
    await redis_client.disconnect()
    logger.info("Shutdown complete")


# ─── Create Application ───

app = FastAPI(
    title="Enterprise AI Support Agent",
    description=(
        "Production-grade RAG + AI Agent Platform with vector retrieval, "
        "tool calling, streaming responses, and full observability."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─── Middleware ───

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# Structured Logging
from app.middleware.logging_middleware import StructuredLoggingMiddleware
app.add_middleware(StructuredLoggingMiddleware)

# Prompt Injection Guard
from app.middleware.injection_guard import InjectionGuardMiddleware
app.add_middleware(InjectionGuardMiddleware, block_injection=False)


# ─── Register Routes ───

from app.auth.router import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.admin import router as admin_router

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(admin_router)


# ─── Root Endpoint ───

@app.get("/")
async def root():
    return {
        "service": "Enterprise AI Support Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
