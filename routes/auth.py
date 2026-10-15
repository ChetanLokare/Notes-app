
import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from pymongo.errors import DuplicateKeyError, PyMongoError

from config.db import con


# =========================================================
# CONFIGURATION
# =========================================================

logger = logging.getLogger(__name__)

auth = APIRouter()
templates = Jinja2Templates(directory="templates")

# Preserve existing MongoDB database and collection names.
db = con["Notes"]
users = db["users"]

# Recommended password hashing configuration from pwdlib.
password_hash = PasswordHash.recommended()

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 254

# Basic email validation. Full RFC email validation is intentionally
# not attempted; email ownership should be verified separately if needed.
EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

# Enforce uniqueness at the database level to prevent duplicate accounts
# even when two registration requests arrive simultaneously.
users.create_index("email", unique=True)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def normalize_email(email: str) -> str:
    """Normalize email consistently before storing or looking it up."""
    return email.strip().lower()


def valid_email(email: str) -> bool:
    """Apply basic email format and length validation."""
    if not email or len(email) > MAX_EMAIL_LENGTH:
        return False

    return bool(EMAIL_PATTERN.fullmatch(email))


def render_auth_page(
    request: Request,
    page: str,
    message: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render an authentication page without caching its response."""
    response = templates.TemplateResponse(
        request=request,
        name=page,
        context={"message": message},
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def redirect_no_cache(url: str) -> RedirectResponse:
    """Redirect without caching authentication-related responses."""
    response = RedirectResponse(url=url, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


def establish_session(request: Request, user: dict) -> None:
    """
    Replace any existing session data after successful authentication.

    Store only the user's identifier and email; never store passwords
    or password hashes in the session.
    """
    request.session.clear()
    request.session["user_id"] = str(user["_id"])
    request.session["email"] = user["email"]


def valid_password_length(password: str) -> bool:
    """Validate the password length in characters."""
    return MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH


# =========================================================
# REGISTRATION
# =========================================================

@auth.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Display the registration page."""
    if request.session.get("user_id"):
        return redirect_no_cache("/")

    return render_auth_page(request, "register.html")


@auth.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Validate registration details and create a new user."""
    email = normalize_email(email)

    # Validate email.
    if not valid_email(email):
        return render_auth_page(
            request,
            "register.html",
            "Enter a valid email address.",
            400,
        )

    # Validate password length before performing expensive hashing.
    if not valid_password_length(password):
        return render_auth_page(
            request,
            "register.html",
            "Password must contain 8–128 characters.",
            400,
        )

    # Do not trim passwords; spaces may intentionally be part of them.
    if password != confirm_password:
        return render_auth_page(
            request,
            "register.html",
            "Passwords do not match.",
            400,
        )

    # Hash the password before saving it. Never store the plaintext password.
    try:
        hashed_password = password_hash.hash(password)
    except (ValueError, TypeError):
        logger.exception("Password hashing failed during registration")
        return render_auth_page(
            request,
            "register.html",
            "Unable to create your account right now. Please try again.",
            500,
        )

    user_document = {
        "email": email,
        "password_hash": hashed_password,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = users.insert_one(user_document)

        # Use the inserted identifier to establish the session.
        new_user = {
            "_id": result.inserted_id,
            "email": email,
        }
        establish_session(request, new_user)

        return redirect_no_cache("/")

    except DuplicateKeyError:
        # The unique database index handles concurrent registration attempts.
        return render_auth_page(
            request,
            "register.html",
            "An account with this email already exists.",
            409,
        )

    except PyMongoError:
        logger.exception("Database error during user registration")
        return render_auth_page(
            request,
            "register.html",
            "Registration is temporarily unavailable. Please try again.",
            503,
        )


# =========================================================
# LOGIN
# =========================================================

@auth.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Display the login page."""
    if request.session.get("user_id"):
        return redirect_no_cache("/")

    return render_auth_page(request, "login.html")


@auth.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Authenticate a user and establish a fresh session."""
    email = normalize_email(email)

    # Apply basic validation before querying MongoDB.
    if not valid_email(email) or not password:
        return render_auth_page(
            request,
            "login.html",
            "Invalid email or password.",
            401,
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        return render_auth_page(
            request,
            "login.html",
            "Invalid email or password.",
            401,
        )

    try:
        user = users.find_one(
            {"email": email},
            {"email": 1, "password_hash": 1},
        )

    except PyMongoError:
        logger.exception("Database error during user login")
        return render_auth_page(
            request,
            "login.html",
            "Login is temporarily unavailable. Please try again.",
            503,
        )

    # Keep the same public error for unknown email and incorrect password.
    if user is None:
        return render_auth_page(
            request,
            "login.html",
            "Invalid email or password.",
            401,
        )

    stored_hash = user.get("password_hash")

    if not isinstance(stored_hash, str) or not stored_hash:
        logger.error(
            "User account has a missing or invalid password hash: %s",
            user.get("_id"),
        )
        return render_auth_page(
            request,
            "login.html",
            "Invalid email or password.",
            401,
        )

    try:
        password_is_valid = password_hash.verify(
            password,
            stored_hash,
        )
    except (ValueError, TypeError):
        # Do not reveal stored hash details to the client.
        logger.exception(
            "Password verification failed for user ID %s",
            user.get("_id"),
        )
        password_is_valid = False

    if not password_is_valid:
        return render_auth_page(
            request,
            "login.html",
            "Invalid email or password.",
            401,
        )

    establish_session(request, user)

    return redirect_no_cache("/")


# =========================================================
# LOGOUT
# =========================================================

@auth.post("/logout")
def logout(request: Request):
    """Clear the current session and redirect to the login page."""
    request.session.clear()
    return redirect_no_cache("/login")
