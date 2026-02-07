"""
API Testing Tool - FastAPI Application Entry Point

A Postman-like API management tool for managing HTTP requests,
collections, environments, and request history.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .exceptions import register_exception_handlers
from .migrations.add_folder_sort_order import migrate as migrate_folder_sort_order
from .migrations.remove_collections import migrate as migrate_remove_collections
from .routers import requests, collections, environments, execute, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup: Initialize database
    init_db()
    # Run migrations for existing databases
    migrate_folder_sort_order()
    migrate_remove_collections()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="API Testing Tool",
    description="A Postman-like API management tool for testing and debugging APIs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS middleware
# Allow all origins for development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers
register_exception_handlers(app)


@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "API Testing Tool",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Register routers
app.include_router(requests.router)
app.include_router(collections.router)
app.include_router(environments.router)
app.include_router(execute.router)
app.include_router(history.router)
