"""
Database helpers shared by the service route handlers.

Part of: backend / data access.

Why its own file: handlers should express intent ("fetch this building or 404",
"save this, and if it collides say 409") rather than repeat try/except blocks
around SQLAlchemy. It is also the one place that knows how PostgreSQL error
codes map onto HTTP status codes, so that mapping stays consistent across four
services.
"""

from sqlalchemy.exc import IntegrityError

from errors import ApiError

# PostgreSQL SQLSTATE codes that a request can legitimately trigger.
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"
CHECK_VIOLATION = "23514"
NOT_NULL_VIOLATION = "23502"
# ON DELETE RESTRICT raises restrict_violation (23001), NOT foreign_key_violation
# (23503) — PostgreSQL distinguishes the two, and handling only 23503 turns a
# legitimate "still in use" conflict into a 500.
RESTRICT_VIOLATION = "23001"
REFERENTIAL_VIOLATIONS = (FOREIGN_KEY_VIOLATION, RESTRICT_VIOLATION)


def get_or_404(session, model, record_id, label):
    """
    Fetch one row by primary key or raise 404.

    Args:
        label: human name used in the error, e.g. "Building".
    """
    record = session.get(model, record_id)
    if record is None:
        raise ApiError(404, f"{label} not found")
    return record


def ensure_exists(session, model, record_id, label):
    """
    Verify a referenced row exists before using its id.

    Checking first turns "building_id points at nothing" into a clear 404 at the
    field that caused it, instead of a foreign-key violation surfacing later as
    a generic 409.
    """
    if record_id is None:
        return None
    return get_or_404(session, model, record_id, label)


def save(session, record, *, conflict=None):
    """
    Flush a pending insert or update, translating database errors to HTTP ones.

    Flushing here rather than waiting for the session to commit means the error
    is raised while the handler can still turn it into a useful message.

    Args:
        conflict: message to use for a uniqueness collision, e.g.
            "A floor with that name already exists in this building".
    """
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise translate_integrity_error(exc, conflict)
    return record


def delete(session, record, label):
    """
    Delete a row, turning a RESTRICT violation into 409 rather than 500.

    This is what makes "you cannot delete a building that still has floors"
    an actionable message instead of a stack trace.
    """
    session.delete(record)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if sqlstate(exc) in REFERENTIAL_VIOLATIONS:
            raise ApiError(409, f"{label} is still referenced by other records and cannot be deleted")
        raise translate_integrity_error(exc, None)


def sqlstate(exc):
    """Extract the PostgreSQL SQLSTATE from a wrapped driver error, if present."""
    return getattr(getattr(exc, "orig", None), "sqlstate", None)


def translate_integrity_error(exc, conflict_message):
    """
    Map a database constraint violation onto the right HTTP status.

    The driver's own message is never returned to the client: it exposes table
    and constraint names, which is more internal structure than a caller needs.
    """
    code = sqlstate(exc)
    if code == UNIQUE_VIOLATION:
        return ApiError(409, conflict_message or "That record already exists")
    if code in REFERENTIAL_VIOLATIONS:
        return ApiError(409, "A referenced record is missing or still in use")
    if code == CHECK_VIOLATION:
        return ApiError(400, "A field failed a database validation rule")
    if code == NOT_NULL_VIOLATION:
        return ApiError(400, "A required field was missing")
    return ApiError(500, "Internal server error")
