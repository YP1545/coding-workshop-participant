"""
Incidents service: incidents, notes, the workflow, and the dashboard.

Part of: backend / incidents service (one Lambda).

Why its own service: incidents are the product's core write path and the one
entity every persona touches. Notes live here because they are meaningless
apart from their incident; the assignment requests and the dashboard live here
because they aggregate the same tables.

The rules themselves are in their own modules and know nothing about the web:
workflow.py (which status moves are legal), access.py (who may see what),
dashboard.py (one summary per persona), assignment_requests.py (filling in
names). This file is only the HTTP shape around them.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from access import can_comment_on, engineer_profile_id, order_for, scope_for, visible_incident
from app import create_app, lambda_handler
from assignment_requests import describe as describe_requests
from crud import delete, ensure_exists, get_or_404, save
from dashboard import build_summary
from deps import (
    ADMIN_ONLY,
    ENGINEER_ONLY,
    get_current_user,
    get_session,
    require_roles,
)
from errors import ApiError
from models import (
    AssignmentRequestStatus,
    Building,
    EngineerProfile,
    Floor,
    Incident,
    IncidentAssignmentRequest,
    IncidentCategory,
    IncidentNote,
    IncidentPriority,
    IncidentStatus,
    Seat,
    User,
    UserRole,
)
from schemas import (
    AssignIn,
    AssignmentRequestOut,
    CategoryOut,
    DecisionIn,
    EscalateIn,
    IncidentIn,
    IncidentOut,
    IncidentPage,
    IncidentUpdateIn,
    NoteIn,
    NoteOut,
    StatusIn,
)
from workflow import change_status, now, record_history

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_NAME = "incidents-service"

# Location columns and the table each points at, used to validate a reference
# before storing it.
LOCATION_FIELDS = (
    ("building_id", Building, "Building"),
    ("floor_id", Floor, "Floor"),
    ("seat_id", Seat, "Seat"),
)

app = create_app(SERVICE_NAME, "ACME Facility Incidents — incidents and dashboard")
router = APIRouter()


def apply_location(session, incident, payload):
    """
    Validate and set the three optional location ids.

    Only fields actually present in the request are touched. The edit form sends
    the fields somebody changed, so writing None for an absent key would quietly
    erase where an incident happened during a rename. An explicit null still
    clears it.

    Each id is checked for existence so a typo is a 404 naming the field, rather
    than a foreign-key violation surfacing as a generic conflict.
    """
    for field, model, label in LOCATION_FIELDS:
        if field not in payload.model_fields_set:
            continue
        value = getattr(payload, field)
        ensure_exists(session, model, value, label)
        setattr(incident, field, value)


def search_condition(term):
    """
    Match a search term against an incident's reference, title or description.

    The reference is matched on a contained substring so that both "INC-0042"
    and "42" find the same incident — somebody reading a number off a screen
    should not have to know the prefix is part of it.

    % and _ mean something inside LIKE, so a search for "50%" would otherwise
    behave as a wildcard and match everything the caller can see — the opposite
    of narrowing. They are escaped here.

    Worth knowing: a leading-wildcard LIKE cannot use a normal index, so this
    scans. Fine at this size; a trigram index is the fix when it is not.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(
        Incident.reference.ilike(pattern, escape="\\"),
        Incident.title.ilike(pattern, escape="\\"),
        Incident.description.ilike(pattern, escape="\\"),
    )


def valid_category(session, slug):
    """
    Check a category exists, or raise 400 naming what is allowed.

    The allowed values live in the incident_categories table now, so Pydantic
    cannot check them — it has no database. Without this the insert would fail
    on the foreign key and surface as a generic 409 about "a referenced record",
    which tells a caller nothing about what to send instead.
    """
    if session.get(IncidentCategory, slug) is not None:
        return slug

    allowed = session.scalars(
        select(IncidentCategory.slug).order_by(IncidentCategory.sort_order)
    ).all()
    raise ApiError(400, f"Unknown category '{slug}'. Allowed: {', '.join(allowed)}")


def is_assigned_engineer(session, user, incident):
    """True if this caller is the engineer the incident is assigned to."""
    if user.role != UserRole.ENGINEER or incident.assignee_id is None:
        return False
    return incident.assignee_id == engineer_profile_id(session, user)


# --- Incidents --------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut], tags=["categories"])
def list_categories(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    The categories an incident can be filed under, in dropdown order.

    Read-only on purpose: adding one is a row a facility admin inserts directly,
    not an endpoint the MVP exposes. Making it writable would need its own
    screen, its own permissions, and a rule for what happens to incidents filed
    under a category somebody renames.
    """
    return session.scalars(
        select(IncidentCategory).order_by(IncidentCategory.sort_order, IncidentCategory.name)
    ).all()


@router.post("/incidents", response_model=IncidentOut, status_code=201, tags=["incidents"])
def create_incident(
    payload: IncidentIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Report an incident. Always starts at open, reported by the caller.

    Open to any signed-in role, not employees alone: an admin who finds a broken
    lift, or an engineer who spots a fault on another job, should be able to
    raise it. A deliberate widening of the plan's contract, noted in project.md.
    """
    incident = Incident(
        title=payload.title,
        description=payload.description,
        category=valid_category(session, payload.category),
        priority=payload.priority,
        reporter_id=user.id,
        status=IncidentStatus.OPEN,
    )
    apply_location(session, incident, payload)
    session.add(incident)
    save(session, incident)

    # The first row of the incident's history: from nothing, to open. Without
    # it the timeline would start at the first status change, and the dashboard
    # could not tell how long an incident sat untouched.
    record_history(session, incident, None, IncidentStatus.OPEN, user.id)

    logger.info("Incident %s reported by %s", incident.id, user.id)
    return incident


@router.get("/incidents", response_model=IncidentPage, tags=["incidents"])
def list_incidents(
    search: str | None = Query(default=None, max_length=200),
    status: IncidentStatus | None = None,
    priority: IncidentPriority | None = None,
    category: str | None = Query(default=None, max_length=50),
    building_id: uuid.UUID | None = None,
    floor_id: uuid.UUID | None = None,
    seat_id: uuid.UUID | None = None,
    reporter_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    escalated: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    List incidents the caller may see, one page at a time.

    The caller's scope is applied first and the filters narrow it further, so a
    crafted query string can only ever subtract. Everything happens in SQL, so
    the indexes are used and the total means something.
    """
    statement = scope_for(session, user, select(Incident))

    if search and search.strip():
        statement = statement.where(search_condition(search.strip()))

    filters = {
        Incident.status: status,
        Incident.priority: priority,
        Incident.category: category,
        Incident.building_id: building_id,
        Incident.floor_id: floor_id,
        Incident.seat_id: seat_id,
        Incident.reporter_id: reporter_id,
        Incident.assignee_id: assignee_id,
    }
    for column, value in filters.items():
        if value is not None:
            statement = statement.where(column == value)

    if escalated is not None:
        statement = statement.where(Incident.escalated == escalated)

    # Counted before paging, so total is how many match rather than how many
    # are on this page.
    total = session.scalar(select(func.count()).select_from(statement.subquery()))

    statement = order_for(user, statement, engineer_profile_id(session, user))
    incidents = session.scalars(statement.limit(limit).offset(offset)).all()

    return {"items": incidents, "total": total or 0, "limit": limit, "offset": offset}


@router.get("/incidents/{incident_id}", response_model=IncidentOut, tags=["incidents"])
def get_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Fetch one incident the caller may see."""
    return visible_incident(session, user, incident_id)


@router.put("/incidents/{incident_id}", response_model=IncidentOut, tags=["incidents"])
def update_incident(
    incident_id: uuid.UUID,
    payload: IncidentUpdateIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Update an incident's descriptive fields.

    Only the reporter or an admin may edit: an engineer works the ticket but
    does not get to rewrite what was reported. Status, assignee and escalation
    are not fields on this model at all — each has its own endpoint that
    enforces the rules and records who did it.
    """
    incident = visible_incident(session, user, incident_id)

    if user.role != UserRole.FACILITY_ADMIN and incident.reporter_id != user.id:
        raise ApiError(403, "Only the reporter or a facility admin can edit this incident")

    incident.title = payload.title
    incident.description = payload.description
    if payload.category is not None:
        incident.category = valid_category(session, payload.category)
    if payload.priority is not None:
        incident.priority = payload.priority
    apply_location(session, incident, payload)
    save(session, incident)
    return incident


@router.delete("/incidents/{incident_id}", status_code=204, tags=["incidents"])
def delete_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Delete an incident.

    Its notes and status history go with it (ON DELETE CASCADE): they describe
    this incident and nothing else.
    """
    incident = get_or_404(session, Incident, incident_id, "Incident")
    delete(session, incident, "Incident")
    logger.info("Incident %s deleted by %s", incident_id, user.id)


# --- Workflow ---------------------------------------------------------------


@router.patch("/incidents/{incident_id}/status", response_model=IncidentOut, tags=["workflow"])
def change_incident_status(
    incident_id: uuid.UUID,
    payload: StatusIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Move an incident to a new status.

    Only the assigned engineer or an admin. The employee who reported it can
    read the status and add notes, but the person doing the work says where it
    has got to. Which moves are legal lives in workflow.py.
    """
    incident = visible_incident(session, user, incident_id)

    if user.role != UserRole.FACILITY_ADMIN and not is_assigned_engineer(session, user, incident):
        raise ApiError(403, "Only the assigned engineer or a facility admin can change the status")

    change_status(session, incident, payload.status, user.id, payload.blocked_reason)
    save(session, incident)
    logger.info("Incident %s moved to %s by %s", incident.id, payload.status.value, user.id)
    return incident


@router.patch("/incidents/{incident_id}/assign", response_model=IncidentOut, tags=["workflow"])
def assign_incident(
    incident_id: uuid.UUID,
    payload: AssignIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Assign an incident to an engineer, or unassign it by sending null.

    The admin's direct route. Engineers can also ask for work through the
    requests below, but an admin should never have to wait for one to push an
    urgent job to somebody.
    """
    incident = get_or_404(session, Incident, incident_id, "Incident")

    if payload.assignee_id is None:
        incident.assignee_id = None
        incident.assigned_at = None
    else:
        profile = ensure_exists(session, EngineerProfile, payload.assignee_id, "Engineer profile")

        # A profile survives a demotion so past work keeps its owner, so the
        # role has to be checked rather than assumed from the profile existing.
        assignee_account = session.get(User, profile.user_id)
        if assignee_account is None or assignee_account.role != UserRole.ENGINEER:
            raise ApiError(409, "That person is no longer an engineer")

        incident.assignee_id = payload.assignee_id
        incident.assigned_at = now()
        # Anybody still waiting to be given this incident no longer can be.
        deny_other_requests(session, incident, keep_request_id=None, decided_by=user.id)

    save(session, incident)
    logger.info("Incident %s assigned to %s by %s", incident.id, payload.assignee_id, user.id)
    return incident


@router.patch("/incidents/{incident_id}/escalate", response_model=IncidentOut, tags=["workflow"])
def escalate_incident(
    incident_id: uuid.UUID,
    payload: EscalateIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Ask for an incident to be escalated, or confirm the escalation.

    Two jobs on one endpoint, split by role: the reporter raises their hand with
    a reason, because "why" is the useful part; only an admin marks it actually
    escalated. Letting anyone set that would make the escalated list meaningless
    within a day.
    """
    incident = visible_incident(session, user, incident_id)
    is_admin = user.role == UserRole.FACILITY_ADMIN

    if "escalated" in payload.model_fields_set and not is_admin:
        raise ApiError(403, "Only a facility admin can confirm an escalation")

    if "escalation_requested" in payload.model_fields_set:
        if not is_admin and incident.reporter_id != user.id:
            raise ApiError(403, "Only the person who reported this incident can request escalation")

        if payload.escalation_requested and not payload.escalation_reason \
                and not incident.escalation_reason:
            raise ApiError(400, "An 'escalation_reason' is required when requesting escalation")

        incident.escalation_requested = bool(payload.escalation_requested)
        if payload.escalation_reason:
            incident.escalation_reason = payload.escalation_reason

    if "escalated" in payload.model_fields_set:
        incident.escalated = bool(payload.escalated)
        if payload.escalation_reason:
            incident.escalation_reason = payload.escalation_reason
        if incident.escalated and not incident.escalation_reason:
            raise ApiError(400, "An 'escalation_reason' is required when escalating an incident")

    save(session, incident)
    return incident


# --- Notes ------------------------------------------------------------------


@router.post("/incidents/{incident_id}/notes", response_model=NoteOut, status_code=201,
             tags=["notes"])
def create_note(
    incident_id: uuid.UUID,
    payload: NoteIn,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Add a note, authored by the caller.

    Writing is narrower than reading. An engineer who can see an unassigned
    incident, so they can judge whether to ask for it, still cannot comment on
    it — the thread belongs to the people actually involved.
    """
    incident = visible_incident(session, user, incident_id)

    if not can_comment_on(session, user, incident):
        raise ApiError(403, "Only the reporter, the assigned engineer or a facility admin can add notes")

    note = IncidentNote(incident_id=incident.id, author_id=user.id, body=payload.body)
    session.add(note)
    save(session, note)
    return note


@router.get("/incidents/{incident_id}/notes", response_model=list[NoteOut], tags=["notes"])
def list_notes(
    incident_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List an incident's notes oldest first, so the thread reads top to bottom."""
    incident = visible_incident(session, user, incident_id)
    return session.scalars(
        select(IncidentNote)
        .where(IncidentNote.incident_id == incident.id)
        .order_by(IncidentNote.created_at)
    ).all()


# --- Assignment requests ----------------------------------------------------


def deny_other_requests(session, incident, keep_request_id, decided_by):
    """
    Deny every pending request for an incident, except the one being approved.

    Once the work has an owner, leaving the others pending would keep showing
    engineers a job that is no longer available.
    """
    pending = session.scalars(
        select(IncidentAssignmentRequest).where(
            IncidentAssignmentRequest.incident_id == incident.id,
            IncidentAssignmentRequest.status == AssignmentRequestStatus.PENDING,
        )
    ).all()

    for other in pending:
        if keep_request_id is not None and other.id == keep_request_id:
            continue
        other.status = AssignmentRequestStatus.DENIED
        other.decided_at = now()
        other.decided_by = decided_by


@router.post("/incidents/{incident_id}/assignment-requests", response_model=AssignmentRequestOut,
             status_code=201, tags=["assignment requests"])
def request_assignment(
    incident_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ENGINEER_ONLY)),
):
    """
    Ask to be given an unassigned incident.

    The unique constraint on (incident_id, engineer_id) makes asking twice a 409
    at the database level, rather than a race between two invocations.
    """
    incident = visible_incident(session, user, incident_id)

    profile_id = engineer_profile_id(session, user)
    if profile_id is None:
        raise ApiError(403, "You need an engineer profile before you can request work")

    if incident.assignee_id is not None:
        raise ApiError(409, "This incident is already assigned")

    assignment_request = IncidentAssignmentRequest(
        incident_id=incident.id, engineer_id=profile_id
    )
    session.add(assignment_request)
    save(session, assignment_request, conflict="You have already requested this incident")
    logger.info("Engineer %s requested incident %s", profile_id, incident.id)
    return describe_requests(session, [assignment_request])[0]


@router.get("/incidents/{incident_id}/assignment-requests",
            response_model=list[AssignmentRequestOut], tags=["assignment requests"])
def list_requests_for_incident(
    incident_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    The requests made for one incident.

    An admin sees all of them, since choosing between them is the point. An
    engineer sees only their own — who else wants the job is not their business.
    """
    incident = visible_incident(session, user, incident_id)

    statement = select(IncidentAssignmentRequest).where(
        IncidentAssignmentRequest.incident_id == incident.id
    )

    if user.role != UserRole.FACILITY_ADMIN:
        profile_id = engineer_profile_id(session, user)
        if profile_id is None:
            return []
        statement = statement.where(IncidentAssignmentRequest.engineer_id == profile_id)

    requests = session.scalars(
        statement.order_by(IncidentAssignmentRequest.requested_at)
    ).all()
    return describe_requests(session, requests)


@router.get("/assignment-requests", response_model=list[AssignmentRequestOut],
            tags=["assignment requests"])
def list_all_requests(
    status: AssignmentRequestStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """The admin's queue: every request across all incidents, newest first."""
    statement = select(IncidentAssignmentRequest)
    if status is not None:
        statement = statement.where(IncidentAssignmentRequest.status == status)

    requests = session.scalars(
        statement.order_by(IncidentAssignmentRequest.requested_at.desc())
        .limit(limit).offset(offset)
    ).all()
    return describe_requests(session, requests)


@router.get("/engineers/me/assignment-requests", response_model=list[AssignmentRequestOut],
            tags=["assignment requests"])
def list_my_requests(
    status: AssignmentRequestStatus | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ENGINEER_ONLY)),
):
    """The engineer's own requests, so they can see what they are waiting on."""
    profile_id = engineer_profile_id(session, user)
    if profile_id is None:
        return []

    statement = select(IncidentAssignmentRequest).where(
        IncidentAssignmentRequest.engineer_id == profile_id
    )
    if status is not None:
        statement = statement.where(IncidentAssignmentRequest.status == status)

    requests = session.scalars(
        statement.order_by(IncidentAssignmentRequest.requested_at.desc())
    ).all()
    return describe_requests(session, requests)


@router.patch("/assignment-requests/{request_id}", response_model=AssignmentRequestOut,
              tags=["assignment requests"])
def decide_assignment_request(
    request_id: uuid.UUID,
    payload: DecisionIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Approve or deny an engineer's request.

    Approving does three things at once — records the decision, assigns the
    incident, and denies everybody else who asked — which is why it is one
    endpoint rather than something the frontend stitches together.
    """
    assignment_request = get_or_404(
        session, IncidentAssignmentRequest, request_id, "Assignment request"
    )

    if assignment_request.status != AssignmentRequestStatus.PENDING:
        raise ApiError(409, f"This request has already been {assignment_request.status.value}")

    if payload.status == AssignmentRequestStatus.PENDING:
        raise ApiError(400, "A decision must be either 'approved' or 'denied'")

    assignment_request.status = payload.status
    assignment_request.decided_at = now()
    assignment_request.decided_by = user.id

    if payload.status == AssignmentRequestStatus.APPROVED:
        incident = get_or_404(session, Incident, assignment_request.incident_id, "Incident")

        if incident.assignee_id is not None:
            raise ApiError(409, "This incident has already been assigned to someone else")

        incident.assignee_id = assignment_request.engineer_id
        incident.assigned_at = now()
        deny_other_requests(session, incident, assignment_request.id, user.id)

    save(session, assignment_request)
    logger.info("Assignment request %s %s by %s", request_id, payload.status.value, user.id)
    return describe_requests(session, [assignment_request])[0]


# --- Dashboard --------------------------------------------------------------


@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    The numbers for whoever is looking.

    Three different dashboards, not one with things hidden: an employee wants to
    know what is happening to their tickets, an engineer what they have to do
    today, an admin how the whole site is doing. dashboard.py has a function per
    persona, and an employee's response does not contain the site-wide figures
    at all.
    """
    return build_summary(session, user, engineer_profile_id(session, user))


app.include_router(router)

handler = lambda_handler(app, SERVICE_NAME)
