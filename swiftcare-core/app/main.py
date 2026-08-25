from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging_config import setup_logging
setup_logging("swiftcare-core")

from app.api.v1.auth import router as auth_router
from app.api.v1.patients import router as patients_router
from app.api.v1.providers import router as providers_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.prescriptions import router as prescriptions_router
from app.api.v1.ai import router as ai_router
from app.core.config import get_settings
from app.core.rate_limit import DualLayerRateLimitMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    DualLayerRateLimitMiddleware,
    global_max_calls=5000,
    client_max_calls=60,
    window_seconds=60,
    path_limits={
        "/health": 500,
        "/docs": 200,
        "/redoc": 200,
        "/openapi.json": 200,
        "/": 100,
    }
)

# Register routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(patients_router, prefix="/api/v1")
app.include_router(providers_router, prefix="/api/v1")
app.include_router(appointments_router, prefix="/api/v1")
app.include_router(prescriptions_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.environment,
    }
    
@app.get("/")
async def root():
    return {"message": "Welcome to the SwiftCare API v1.0.0 - Please use /docs for API documentation."}