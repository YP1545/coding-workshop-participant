"""
The incident status workflow: which moves are allowed, and what each one records.

Part of: backend / incidents service (business rules).

Why its own file: the rules about how an incident moves through its five
statuses are the heart of the product, and they are easier to read — and to
change — when they are not mixed in with HTTP handling. function.py deals with
requests and responses; this file only knows about incidents.
"""

from datetime import datetime, timezone

from models import IncidentStatus, IncidentStatusHistory
from errors import ApiError

# Which statuses you can move to, from each status.
#
# Read it as: "an open incident can become in_progress, blocked or closed".
# Anything not listed is rejected, so there is no way to jump straight from
# open to resolved without someone actually working on it.
#
# closed has an empty list on purpose: it is the end of the line. Reopening
# would blur the resolution times the dashboard reports, so a new problem gets
# a new incident.
ALLOWED_TRANSITIONS = {
    IncidentStatus.OPEN: [IncidentStatus.IN_PROGRESS, IncidentStatus.BLOCKED, IncidentStatus.CLOSED],
    IncidentStatus.IN_PROGRESS: [IncidentStatus.BLOCKED, IncidentStatus.RESOLVED, IncidentStatus.OPEN],
    IncidentStatus.BLOCKED: [IncidentStatus.IN_PROGRESS, IncidentStatus.OPEN, IncidentStatus.CLOSED],
    IncidentStatus.RESOLVED: [IncidentStatus.CLOSED, IncidentStatus.IN_PROGRESS],
    IncidentStatus.CLOSED: [],
}


def now():
    """The current time, with a timezone attached."""
    return datetime.now(timezone.utc)


def check_transition(old_status, new_status):
    """
    Raise a 400 if this move is not allowed.

    Args:
        old_status (IncidentStatus): where the incident is now.
        new_status (IncidentStatus): where the caller wants it to go.
    """
    allowed = ALLOWED_TRANSITIONS[old_status]

    if not allowed:
        raise ApiError(400, f"An incident that is {old_status.value} cannot change status")

    if new_status not in allowed:
        options = ", ".join(status.value for status in allowed)
        raise ApiError(
            400,
            f"Cannot move an incident from {old_status.value} to {new_status.value}. "
            f"Allowed from here: {options}",
        )


def record_history(session, incident, old_status, new_status, changed_by):
    """
    Write one row saying who moved the incident, from what, to what, and when.

    This table is what makes the dashboard's timing numbers real instead of
    guessed, so every status change writes a row — no exceptions.
    """
    entry = IncidentStatusHistory(
        incident_id=incident.id,
        from_status=old_status,
        to_status=new_status,
        changed_by=changed_by,
    )
    session.add(entry)
    return entry


def stamp_timestamps(incident, new_status):
    """
    Fill in the lifecycle timestamp that goes with this status.

    acknowledged_at is only set the first time an incident is picked up. If it
    were overwritten every time work restarted, "how long until someone looked
    at it" would drift later and later and stop meaning anything.
    """
    if new_status == IncidentStatus.IN_PROGRESS and incident.acknowledged_at is None:
        incident.acknowledged_at = now()

    if new_status == IncidentStatus.RESOLVED:
        incident.resolved_at = now()

    if new_status == IncidentStatus.CLOSED:
        incident.closed_at = now()


def change_status(session, incident, new_status, changed_by, blocked_reason=None):
    """
    Move an incident to a new status, with all the bookkeeping that implies.

    Checks the move is allowed, requires a reason when blocking, updates the
    timestamps, and records the change in the history table.

    Args:
        session: the database session for this request.
        incident (Incident): the incident being moved.
        new_status (IncidentStatus): the status to move to.
        changed_by (uuid.UUID): the id of the user making the change.
        blocked_reason (str, optional): required when new_status is blocked.
    """
    old_status = incident.status

    if new_status == old_status:
        raise ApiError(400, f"This incident is already {old_status.value}")

    check_transition(old_status, new_status)

    # The brief asks specifically why something is blocked, so the reason is
    # required rather than optional.
    if new_status == IncidentStatus.BLOCKED:
        if not blocked_reason:
            raise ApiError(400, "A 'blocked_reason' is required when blocking an incident")
        incident.blocked_reason = blocked_reason

    # Leaving the old reason behind would be confusing once work has restarted.
    if old_status == IncidentStatus.BLOCKED and new_status != IncidentStatus.BLOCKED:
        incident.blocked_reason = None

    incident.status = new_status
    stamp_timestamps(incident, new_status)
    record_history(session, incident, old_status, new_status, changed_by)
