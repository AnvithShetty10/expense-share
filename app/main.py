"""FastAPI application entry point"""

import json

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for expense sharing application",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
if settings.allowed_origins:
    # Parse allowed_origins if it's a JSON string
    if isinstance(settings.allowed_origins, str):
        # If it's a string, split it
        allowed_origins = [
            origin.strip() for origin in settings.allowed_origins.split(",")
        ]
    elif isinstance(settings.allowed_origins, list):
        # If it's already a list, use it directly (and maybe strip elements just in case)
        allowed_origins = [origin.strip() for origin in settings.allowed_origins]
    else:
        # Default to an empty list or raise an error for unknown types
        allowed_origins = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": exc.error_type,
                "path": str(request.url.path),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    # Log the exception (would use proper logging in production)
    print(f"Unhandled exception: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {"message": "Internal server error", "type": "InternalServerError"}
        },
    )


# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - redirects to docs"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs_url": "/docs",
        "version": "1.0.0",
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
