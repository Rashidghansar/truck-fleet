from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .config import settings
from .database import init_db
from .api.v1 import auth, bookings, opportunities, trucks, drivers, gate, dashboard, websocket, trips, bays
from .middleware.error_handler import add_exception_handlers
from .middleware.rate_limit import rate_limit_middleware

# Initialize database tables
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add exception handlers
add_exception_handlers(app)

# Add response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS configuration - use specific origins in production
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# Add rate limiting middleware
if settings.RATE_LIMIT_ENABLED:
    app.middleware("http")(rate_limit_middleware)

# Mount uploads directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(bookings.router, prefix="/api/v1/bookings", tags=["Bookings"])
app.include_router(opportunities.router, prefix="/api/v1/opportunities", tags=["Opportunities"])
app.include_router(trucks.router, prefix="/api/v1/trucks", tags=["Trucks"])
app.include_router(drivers.router, prefix="/api/v1/drivers", tags=["Drivers"])
app.include_router(gate.router, prefix="/api/v1/gate", tags=["Gate Operations"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])
app.include_router(trips.router, prefix="/api/v1/trips", tags=["Trips"])
app.include_router(bays.router, prefix="/api/v1/bays", tags=["Bay Management"])

# New routers
from .api.v1 import documents, ratings, payments, security_officers
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(ratings.router, prefix="/api/v1/ratings", tags=["Ratings & Reviews"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(security_officers.router, prefix="/api/v1/security-officers", tags=["Security Officers"])

@app.get("/")
async def root():
    return {
        "message": "CFS Transport API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS}")
    logger.info(f"Rate Limiting: {'Enabled' if settings.RATE_LIMIT_ENABLED else 'Disabled'}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Shutting down...")
