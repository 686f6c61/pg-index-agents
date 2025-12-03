"""
PG Index Agents - Punto de entrada principal
https://github.com/686f6c61/pg-index-agents

Este modulo configura y arranca la aplicacion FastAPI que sirve como backend
del sistema de agentes. Define la configuracion de CORS para el frontend
Next.js, registra los manejadores de excepciones globales, y gestiona el
ciclo de vida de la aplicacion.

Endpoints raiz disponibles:

    GET / - Informacion basica del servicio
    GET /health - Estado de salud y conectividad con PostgreSQL

El servidor se ejecuta por defecto en localhost:8000 y puede configurarse
mediante las variables de entorno API_HOST y API_PORT.

Ciclo de vida de la aplicacion:

    1. Startup: Valida configuracion y registra advertencias
    2. Running: Procesa peticiones HTTP en /api/*
    3. Shutdown: Cierra conexiones a base de datos

Autor: 686f6c61
Licencia: MIT
"""

import logging
import sys
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from core.config import settings, validate_settings
from core.database import db_manager
from core.state import state_db
from api.routes import router, APIError

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup - validate settings
    warnings = validate_settings()
    for warning in warnings:
        logger.warning(warning)
        state_db.log("system", "WARNING", warning)

    logger.info("Application starting up")
    state_db.log("system", "INFO", "Application starting up")

    yield

    # Shutdown
    db_manager.close()
    logger.info("Application shutting down")
    state_db.log("system", "INFO", "Application shutting down")


app = FastAPI(
    title="PostgreSQL Index Agents",
    description="Intelligent agents for PostgreSQL index analysis and maintenance",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


# Global exception handler
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """Handle custom API errors."""
    logger.error(f"API Error: {exc.detail} ({exc.error_type})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_type,
            "detail": exc.detail,
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    error_id = id(exc)
    logger.error(f"Unhandled exception [{error_id}]: {str(exc)}\n{traceback.format_exc()}")
    state_db.log("system", "ERROR", f"Unhandled exception: {str(exc)[:200]}")

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An unexpected error occurred",
            "error_id": error_id,
            "path": str(request.url.path)
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "PostgreSQL Index Agents",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_status = db_manager.test_connection()
    return {
        "status": "healthy" if db_status["status"] == "connected" else "degraded",
        "database": db_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
