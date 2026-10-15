
import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# =========================================================
# CONFIGURATION
# =========================================================

logger = logging.getLogger(__name__)

# Load environment variables from .env when present.
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip()

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is missing. "
        "Set it in your environment or .env file."
    )


# =========================================================
# MONGODB CLIENT
# =========================================================

con = MongoClient(
    MONGO_URI,
    tz_aware=True,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=10000,
    maxPoolSize=50,
    minPoolSize=0,
    retryReads=True,
    retryWrites=True,
)

# Preserve the existing database and collection names.
db = con["Notes"]
collection = db["notes"]
users_collection = db["users"]


# =========================================================
# CONNECTION HEALTH CHECK
# =========================================================

def check_database_connection() -> bool:
    """
    Verify that MongoDB is reachable.

    MongoClient connects lazily, so creating the client alone
    does not confirm that the database is available.
    """
    try:
        con.admin.command("ping")
        return True

    except PyMongoError:
        logger.exception("MongoDB connection health check failed")
        return False


# =========================================================
# CONNECTION CLEANUP
# =========================================================

def close_database_connection() -> None:
    """Close the MongoDB client and release its connection pool."""
    con.close()
