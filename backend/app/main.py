"""App entry point: wires up CORS, security headers, error handling and routers."""
import os
import socket

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.errors import install_error_handlers
from app.routers import auth, orders, restaurants, staff

settings = get_settings()
# Name of this running copy of the API. Shown in the X-Instance header.
INSTANCE = settings.instance_name or f"{socket.gethostname()}-{os.getpid()}"

app = FastAPI(
    title="Food Delivery API",
    version="1.0.0",
    # Interactive docs are handy locally but switched off in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

install_error_handlers(app)

# CORS: only our own frontend may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,  # needed so the browser sends the refresh cookie
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

DOCS_PATHS = {"/docs", "/openapi.json"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["X-Instance"] = INSTANCE
    if request.url.path not in DOCS_PATHS:  # Swagger UI needs to load its own scripts
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.cookie_secure:  # only meaningful over HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/health", tags=["meta"])
def health():
    """Liveness: this process is running."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["meta"])
def ready():
    """Readiness: this instance can reach the database. The load balancer calls this every
    couple of seconds and stops sending traffic to an instance that answers 503."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)  # no details on purpose
    return {"status": "ready", "instance": INSTANCE}


app.include_router(auth.router)
app.include_router(restaurants.router)
app.include_router(orders.router)
app.include_router(staff.router)
