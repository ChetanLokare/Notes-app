
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware


# =========================================================
# PATHS AND CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Load .env from the project root, independently of the shell's
# current working directory.
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)

SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()

if not SESSION_SECRET:
    raise RuntimeError(
        "SESSION_SECRET is missing. "
        "Add a randomly generated SESSION_SECRET to the project .env file."
    )

if len(SESSION_SECRET) < 32:
    raise RuntimeError(
        "SESSION_SECRET is too short. "
        "Generate a secure random secret of at least 32 characters."
    )

SESSION_HTTPS_ONLY = (
    os.getenv("SESSION_HTTPS_ONLY", "false").strip().lower() == "true"
)

SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours


# =========================================================
# DATABASE
# =========================================================

from config.db import check_database_connection, close_database_connection


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Check database connectivity at startup and close the client
    during shutdown.
    """
    logger.info("Starting My Notes application")

    try:
        if not check_database_connection():
            raise RuntimeError(
                "MongoDB is unavailable. Check MONGO_URI, "
                "network access, and database credentials."
            )

        logger.info("MongoDB connection check successful")

        yield

    finally:
        close_database_connection()
        logger.info("My Notes application shut down")


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="My Notes",
    description="A private notes application with user authentication.",
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# SESSION MIDDLEWARE
# =========================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="my_notes_session",
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)


# =========================================================
# STATIC FILES
# =========================================================

if not STATIC_DIR.is_dir():
    raise RuntimeError(
        f"Static directory not found: {STATIC_DIR}"
    )

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# =========================================================
# ROUTERS
# =========================================================

from routes.auth import auth as auth_router
from routes.note import note as note_router

app.include_router(auth_router)
app.include_router(note_router)


# =========================================================
# HEALTH ENDPOINTS
# =========================================================

@app.get("/health")
def health_check():
    """
    Lightweight liveness check.

    Indicates that the application process is responding;
    it does not guarantee that MongoDB is available.
    """
    return {
        "status": "ok",
        "application": "My Notes",
    }


@app.get("/health/ready")
def readiness_check():
    """
    Readiness check for the application and MongoDB connection.
    """
    if not check_database_connection():
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "application": "My Notes",
                "database": "unavailable",
            },
        )

    return {
        "status": "ready",
        "application": "My Notes",
        "database": "connected",
    }
