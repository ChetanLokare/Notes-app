
from datetime import datetime, timezone
from typing import Any, Iterable


# =========================================================
# DATETIME SERIALIZATION
# =========================================================

def serialize_datetime(value: Any) -> str:
    """
    Convert a datetime to a UTC ISO 8601 string.

    Returns an empty string for missing or invalid datetime values.
    Naive datetimes are treated as UTC for consistency with existing data.
    """
    if not isinstance(value, datetime):
        return ""

    try:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc).isoformat()

    except (ValueError, OverflowError, TypeError):
        return ""


# =========================================================
# BOOLEAN NORMALIZATION
# =========================================================

def serialize_boolean(value: Any, default: bool = False) -> bool:
    """
    Normalize common boolean representations.

    This prevents values such as the string 'false' from accidentally
    becoming True when passed to Python's bool() function.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "1", "yes"}:
            return True

        if normalized in {"false", "0", "no", ""}:
            return False

    return default


# =========================================================
# SINGLE NOTE SERIALIZATION
# =========================================================

def noteEntity(item: dict[str, Any]) -> dict[str, Any]:
    """
    Serialize one MongoDB note document into a frontend-friendly dict.

    The output retains the field names used by the existing frontend:
    id, title, note, important, created_on, updated_status, updated_date.
    """
    updated_date = item.get("updated_date")

    # Older documents may not contain updated_status.
    # In that case, infer it from whether an update timestamp exists.
    updated_status_value = item.get("updated_status")

    if updated_status_value is None:
        updated_status_value = updated_date is not None

    return {
        "id": str(item.get("_id", "")),
        "title": item.get("title", "")
        if isinstance(item.get("title", ""), str)
        else "",
        "note": item.get("note", "")
        if isinstance(item.get("note", ""), str)
        else "",
        "important": serialize_boolean(
            item.get("important", False)
        ),
        "created_on": serialize_datetime(
            item.get("created_on")
        ),
        "updated_status": serialize_boolean(
            updated_status_value
        ),
        "updated_date": serialize_datetime(
            updated_date
        ),
    }


# =========================================================
# MULTIPLE NOTES SERIALIZATION
# =========================================================

def notesEntity(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize an iterable of MongoDB note documents."""
    return [noteEntity(item) for item in items]
