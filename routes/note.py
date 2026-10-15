
import logging
import re
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo import DESCENDING, ASCENDING
from pymongo.errors import PyMongoError

from config.db import con, collection
from schemas.schemas import noteEntity, notesEntity


# =========================================================
# CONFIGURATION
# =========================================================

logger = logging.getLogger(__name__)

note = APIRouter()
templates = Jinja2Templates(directory="templates")

db = con["Notes"]
users = db["users"]

MAX_TITLE_LENGTH = 200
MAX_NOTE_LENGTH = 10_000
MAX_SEARCH_LENGTH = 200
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

SORT_OPTIONS = {
    "newest": [("created_on", DESCENDING)],
    "oldest": [("created_on", ASCENDING)],
    "updated": [("updated_date", DESCENDING), ("created_on", DESCENDING)],
    "title-asc": [("title", ASCENDING)],
    "title-desc": [("title", DESCENDING)],
}


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def get_current_user(request: Request) -> dict[str, Any] | None:
    """
    Retrieve the authenticated user from the database.

    The session contains only the user's ID and email.
    The database remains the source of truth for the account.
    """
    session_user_id = request.session.get("user_id")

    if not isinstance(session_user_id, str):
        return None

    if not ObjectId.is_valid(session_user_id):
        request.session.clear()
        return None

    try:
        user = users.find_one(
            {"_id": ObjectId(session_user_id)},
            {"email": 1},
        )
    except PyMongoError:
        logger.exception("Failed to retrieve authenticated user")
        raise HTTPException(
            status_code=503,
            detail="The service is temporarily unavailable.",
        )

    if user is None:
        request.session.clear()
        return None

    return user


def require_form_user(request: Request) -> dict[str, Any] | RedirectResponse:
    """Require authentication for browser-based form routes."""
    user = get_current_user(request)

    if user is None:
        return RedirectResponse("/login", status_code=303)

    return user


def require_api_user(request: Request) -> dict[str, Any]:
    """Require authentication for JSON/API routes."""
    user = get_current_user(request)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    return user


# =========================================================
# VALIDATION HELPERS
# =========================================================

def get_object_id(note_id: str) -> ObjectId:
    """Validate a note ID before using it in a database query."""
    if not ObjectId.is_valid(note_id):
        raise HTTPException(
            status_code=404,
            detail="Note not found.",
        )

    return ObjectId(note_id)


def owned_note_filter(
    note_id: str,
    user_id: ObjectId,
) -> dict[str, Any]:
    """
    Build a query that matches both the note ID and its owner.

    This prevents one user from reading, updating, or deleting
    another user's notes by changing an ID in a request.
    """
    return {
        "_id": get_object_id(note_id),
        "user_id": user_id,
    }


def validate_note_fields(title: str, content: str) -> tuple[str, str]:
    """Normalize and validate a note's title and content."""
    title = title.strip()
    content = content.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Title cannot be empty.",
        )

    if len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Title cannot exceed {MAX_TITLE_LENGTH} characters.",
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Note content cannot be empty.",
        )

    if len(content) > MAX_NOTE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Note content cannot exceed {MAX_NOTE_LENGTH} characters.",
        )

    return title, content


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def parse_boolean_filter(value: str | None) -> bool | None:
    """Parse optional true/false filters."""
    if value is None or value.strip().lower() in ("", "all"):
        return None

    normalized = value.strip().lower()

    if normalized in ("true", "1", "yes"):
        return True

    if normalized in ("false", "0", "no"):
        return False

    raise HTTPException(
        status_code=400,
        detail="Invalid filter value.",
    )


def parse_date_filter(value: str | None) -> dict[str, Any] | None:
    """
    Parse YYYY, YYYY-MM, or YYYY-MM-DD into a UTC date range.

    The upper bound is exclusive, avoiding end-of-day precision issues.
    """
    if value is None or not value.strip():
        return None

    value = value.strip()

    try:
        if re.fullmatch(r"\d{4}", value):
            year = int(value)
            start = datetime(year, 1, 1, tzinfo=timezone.utc)

            if year == 9999:
                end = datetime.max.replace(tzinfo=timezone.utc)
            else:
                end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

        elif re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = map(int, value.split("-"))
            start = datetime(year, month, 1, tzinfo=timezone.utc)

            if month == 12:
                if year == 9999:
                    end = datetime.max.replace(tzinfo=timezone.utc)
                else:
                    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            start = datetime.strptime(value, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            end = datetime.max.replace(tzinfo=timezone.utc) if (
                start.year == 9999
                and start.month == 12
                and start.day == 31
            ) else start.replace(
                day=start.day
            )

            if end != datetime.max.replace(tzinfo=timezone.utc):
                from datetime import timedelta
                end = start + timedelta(days=1)

        else:
            raise ValueError("Unsupported date format")

    except (ValueError, OverflowError):
        raise HTTPException(
            status_code=400,
            detail="Invalid date. Use YYYY, YYYY-MM, or YYYY-MM-DD.",
        )

    return {"$gte": start, "$lt": end}


def build_search_query(
    user_id: ObjectId,
    q: str | None = None,
    created_on: str | None = None,
    updated_date: str | None = None,
    important: str | None = None,
    updated_status: str | None = None,
) -> dict[str, Any]:
    """Build a search query that always restricts results to one user."""
    conditions: list[dict[str, Any]] = [
        {"user_id": user_id}
    ]

    if q and q.strip():
        search_text = q.strip()

        if len(search_text) > MAX_SEARCH_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Search cannot exceed {MAX_SEARCH_LENGTH} characters.",
            )

        # Escape user input so it is treated as literal text, not regex syntax.
        escaped_text = re.escape(search_text)

        conditions.append({
            "$or": [
                {"title": {"$regex": escaped_text, "$options": "i"}},
                {"note": {"$regex": escaped_text, "$options": "i"}},
            ]
        })

    created_range = parse_date_filter(created_on)
    if created_range is not None:
        conditions.append({"created_on": created_range})

    updated_range = parse_date_filter(updated_date)
    if updated_range is not None:
        conditions.append({"updated_date": updated_range})

    important_value = parse_boolean_filter(important)
    if important_value is not None:
        conditions.append({"important": important_value})

    updated_value = parse_boolean_filter(updated_status)
    if updated_value is not None:
        conditions.append({"updated_status": updated_value})

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def get_sort_order(sort: str) -> list[tuple[str, int]]:
    """Return a supported MongoDB sort order."""
    return SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])


def render_home(
    request: Request,
    user: dict[str, Any],
) -> HTMLResponse:
    """Load the current user's notes and render the main page."""
    try:
        cursor = (
            collection.find({"user_id": user["_id"]})
            .sort(get_sort_order("newest"))
        )
        serialized_notes = notesEntity(list(cursor))

    except PyMongoError:
        logger.exception("Failed to load notes for user %s", user["_id"])
        raise HTTPException(
            status_code=503,
            detail="Unable to load notes right now. Please try again.",
        )

    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "newDocs": serialized_notes,
            "user": {"email": user.get("email", "")},
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# =========================================================
# HOME / LIST NOTES
# =========================================================

@note.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Display the authenticated user's notes."""
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    return render_home(request, user)


# =========================================================
# CREATE NOTE
# =========================================================

@note.post("/")
def create_note(
    request: Request,
    title: str = Form(...),
    note: str = Form(...),
    important: bool = Form(False),
):
    """Create a note owned by the authenticated user."""
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    try:
        title, content = validate_note_fields(title, note)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    now = utc_now()

    document = {
        "user_id": user["_id"],
        "title": title,
        "note": content,
        "important": important,
        "created_on": now,
        "updated_status": False,
        "updated_date": None,
    }

    try:
        collection.insert_one(document)
    except PyMongoError:
        logger.exception("Failed to create a note for user %s", user["_id"])
        raise HTTPException(
            status_code=503,
            detail="Unable to save the note right now. Please try again.",
        )

    return RedirectResponse("/", status_code=303)


# =========================================================
# SEARCH / FILTER / SORT / PAGINATION
# =========================================================

@note.get("/notes/search")
def search_notes(
    request: Request,
    q: str | None = Query(default=None, max_length=MAX_SEARCH_LENGTH),
    created_on: str | None = Query(default=None, max_length=10),
    updated_date: str | None = Query(default=None, max_length=10),
    important: str | None = Query(default=None, max_length=5),
    updated_status: str | None = Query(default=None, max_length=5),
    sort: str = Query(default="newest", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """Search the authenticated user's notes with filters and pagination."""
    user = require_api_user(request)

    try:
        query = build_search_query(
            user_id=user["_id"],
            q=q,
            created_on=created_on,
            updated_date=updated_date,
            important=important,
            updated_status=updated_status,
        )

        total = collection.count_documents(query)
        total_pages = (total + page_size - 1) // page_size
        skip = (page - 1) * page_size

        cursor = (
            collection.find(query)
            .sort(get_sort_order(sort))
            .skip(skip)
            .limit(page_size)
        )

        items = notesEntity(list(cursor))

    except HTTPException:
        raise

    except PyMongoError:
        logger.exception("Note search failed for user %s", user["_id"])
        raise HTTPException(
            status_code=503,
            detail="Unable to search notes right now. Please try again.",
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "sort": sort if sort in SORT_OPTIONS else "newest",
    }


# =========================================================
# TOGGLE IMPORTANT
# =========================================================

@note.post("/toggle_important/{note_id}")
def toggle_important(
    request: Request,
    note_id: str,
):
    """Toggle the importance flag for a note owned by the current user."""
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    query = owned_note_filter(note_id, user["_id"])

    try:
        existing_note = collection.find_one(query)

        if existing_note is None:
            raise HTTPException(
                status_code=404,
                detail="Note not found.",
            )

        new_important_value = not bool(existing_note.get("important", False))

        collection.update_one(
            query,
            {
                "$set": {
                    "important": new_important_value,
                    "updated_status": True,
                    "updated_date": utc_now(),
                }
            },
        )

    except HTTPException:
        raise

    except PyMongoError:
        logger.exception("Failed to toggle importance for note %s", note_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to update the note right now. Please try again.",
        )

    return RedirectResponse("/", status_code=303)


# =========================================================
# EDIT NOTE
# =========================================================

@note.get("/edit_note/{note_id}")
def edit_note_page(
    request: Request,
    note_id: str,
):
    """
    Validate ownership before returning to the main page.

    The existing interface uses inline editing, so this route does not
    depend on a separate edit_note.html template.
    """
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    query = owned_note_filter(note_id, user["_id"])

    try:
        existing_note = collection.find_one(query)
    except PyMongoError:
        logger.exception("Failed to retrieve note %s for editing", note_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to open the note right now. Please try again.",
        )

    if existing_note is None:
        raise HTTPException(status_code=404, detail="Note not found.")

    return RedirectResponse("/", status_code=303)


@note.post("/edit_note/{note_id}")
def edit_note(
    request: Request,
    note_id: str,
    title: str = Form(...),
    note: str = Form(...),
    important: bool = Form(False),
):
    """Update a note only if it belongs to the authenticated user."""
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    query = owned_note_filter(note_id, user["_id"])

    try:
        title, content = validate_note_fields(title, note)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    update_document = {
        "$set": {
            "title": title,
            "note": content,
            "important": important,
            "updated_status": True,
            "updated_date": utc_now(),
        }
    }

    try:
        result = collection.update_one(query, update_document)

        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Note not found.",
            )

    except HTTPException:
        raise

    except PyMongoError:
        logger.exception("Failed to edit note %s", note_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to update the note right now. Please try again.",
        )

    return RedirectResponse("/", status_code=303)


# =========================================================
# DELETE NOTE
# =========================================================

@note.post("/delete_note/{note_id}")
def delete_note(
    request: Request,
    note_id: str,
):
    """Delete a note only if it belongs to the authenticated user."""
    user = require_form_user(request)

    if isinstance(user, RedirectResponse):
        return user

    query = owned_note_filter(note_id, user["_id"])

    try:
        result = collection.delete_one(query)

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Note not found.",
            )

    except HTTPException:
        raise

    except PyMongoError:
        logger.exception("Failed to delete note %s", note_id)
        raise HTTPException(
            status_code=503,
            detail="Unable to delete the note right now. Please try again.",
        )

    return RedirectResponse("/", status_code=303)
