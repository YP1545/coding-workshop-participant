"""
The numbers behind /dashboard/summary, one set per persona.

Part of: backend / incidents service (reporting).

Why its own file: the three people using this product open the dashboard for
three different reasons, so they get three different answers.

  * an employee wants to know what is happening to the problems they reported
  * an engineer wants to know what they have to do today
  * a facility admin wants to know how the whole site is doing

Writing one summary that tried to serve all three would end up serving none of
them well, so there is a function per persona below and build_summary picks.
Everything is filtered on the server: the response only ever contains figures
the caller is entitled to see.
"""

from sqlalchemy import func, select

from models import (
    AssignmentRequestStatus,
    AvailabilityStatus,
    Building,
    EngineerProfile,
    Incident,
    IncidentAssignmentRequest,
    IncidentNote,
    IncidentStatus,
    User,
    UserRole,
)

# How many locations to include in the "where do problems keep happening" list.
TOP_LOCATIONS_LIMIT = 5

# How many incidents to list inline on a dashboard before it stops being a
# summary and starts being the incident page.
LIST_LIMIT = 10

# The statuses that still need somebody to do something.
ACTIVE_STATUSES = (IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS, IncidentStatus.BLOCKED)


def count_by(session, column, conditions):
    """
    Count incidents grouped by one column.

    Args:
        column: the column to group by, e.g. Incident.status.
        conditions (list): WHERE clauses limiting which incidents are counted.
            An empty list means every incident, which only an admin ever gets.

    Returns:
        dict: the column value as a string, mapped to how many incidents have
            it — for example {"open": 4, "closed": 1}.
    """
    statement = select(column, func.count(Incident.id)).where(*conditions).group_by(column)
    rows = session.execute(statement).all()

    counts = {}
    for value, total in rows:
        # Status and priority come back as enum members, ids as UUIDs. Both have
        # to be strings to survive being turned into JSON.
        if value is None:
            key = "unassigned"
        elif hasattr(value, "value"):
            key = value.value
        else:
            key = str(value)
        counts[key] = total

    return counts


def average_hours(session, end_column, conditions):
    """
    Average hours from an incident being reported to a later milestone.

    Only incidents that reached the milestone are counted. An incident nobody
    has resolved yet has no resolution time, and treating it as zero would make
    the team look faster the more work they left undone.

    Returns:
        float | None: hours to one decimal place, or None if nothing has
            reached this milestone yet.
    """
    statement = select(Incident.created_at, end_column).where(
        end_column.is_not(None), *conditions
    )
    rows = session.execute(statement).all()

    if not rows:
        return None

    total_hours = 0.0
    for created_at, reached_at in rows:
        total_hours += (reached_at - created_at).total_seconds() / 3600

    return round(total_hours / len(rows), 1)


def incident_summary(incident):
    """A short form of an incident, for the lists shown on a dashboard."""
    return {
        "id": str(incident.id),
        # The number somebody would quote when asking about this one.
        "reference": incident.reference,
        "title": incident.title,
        "status": incident.status.value,
        "priority": incident.priority.value,
        # category is a plain slug now, not an enum member — it is a foreign key
        # to incident_categories rather than a database enum type.
        "category": incident.category,
        "created_at": incident.created_at.isoformat(),
    }


# --- Employee ---------------------------------------------------------------


def awaiting_employee(session, user):
    """
    The employee's incidents where somebody else spoke last.

    This is the closest thing to a notification in a product with no email or
    Slack: if an engineer left a note, it is waiting to be read. Answering
    "how effectively are employees informed" with a dashboard that is correct
    whenever they look at it, rather than a message that might be missed.

    Returns:
        list[dict]: incidents whose most recent note came from someone else.
    """
    mine = session.scalars(
        select(Incident).where(Incident.reporter_id == user.id)
    ).all()
    if not mine:
        # Same (count, list) shape as the normal path. Returning a bare list
        # here crashed the dashboard for anyone who had not reported anything
        # yet — which is everybody on their first day.
        return 0, []

    by_id = {incident.id: incident for incident in mine}

    # Every note on those incidents, oldest first, so the last one seen for each
    # incident is its most recent. One query rather than one per incident.
    notes = session.scalars(
        select(IncidentNote)
        .where(IncidentNote.incident_id.in_(by_id.keys()))
        .order_by(IncidentNote.created_at)
    ).all()

    last_author = {}
    for note in notes:
        last_author[note.incident_id] = note.author_id

    waiting = [
        by_id[incident_id]
        for incident_id, author_id in last_author.items()
        if author_id != user.id
    ]
    waiting.sort(key=lambda incident: incident.created_at, reverse=True)
    # The count and the list are returned separately on purpose. The list is
    # capped so the dashboard stays a summary; taking its length as the count
    # would quietly report "10" to someone who has 40 waiting.
    return len(waiting), [incident_summary(incident) for incident in waiting[:LIST_LIMIT]]


def employee_summary(session, user):
    """What an employee sees: their own tickets, and which ones need reading."""
    mine = [Incident.reporter_id == user.id]
    awaiting_count, awaiting = awaiting_employee(session, user)

    return {
        "role": UserRole.EMPLOYEE.value,
        "counts_by_status": count_by(session, Incident.status, mine),
        "counts_by_priority": count_by(session, Incident.priority, mine),
        "awaiting_count": awaiting_count,
        "awaiting_your_attention": awaiting,
    }


# --- Engineer ---------------------------------------------------------------


def engineer_summary(session, user, profile_id):
    """
    What an engineer sees: their workload, and what they could pick up.

    Counts cover work actually assigned to them. Unassigned incidents they are
    allowed to browse are reported separately — mixing the two would make their
    own queue look bigger than it is.
    """
    if profile_id is None:
        # The engineer role without an engineer profile: they can sign in and
        # look around, but nothing can be assigned to them yet.
        return {
            "role": UserRole.ENGINEER.value,
            "counts_by_status": {},
            "counts_by_priority": {},
            "active_count": 0,
            "assigned_incidents": [],
            "my_pending_requests": 0,
            "open_to_request": 0,
            "avg_hours_to_resolve": None,
            "needs_profile": True,
        }

    assigned = [Incident.assignee_id == profile_id]

    active_conditions = [
        Incident.assignee_id == profile_id,
        Incident.status.in_(ACTIVE_STATUSES),
    ]

    # Counted in SQL, listed with a cap. An engineer with 40 open jobs must see
    # 40 on the card even though only the newest 10 are listed beneath it.
    active_count = session.scalar(
        select(func.count(Incident.id)).where(*active_conditions)
    )

    active = session.scalars(
        select(Incident)
        .where(*active_conditions)
        .order_by(Incident.created_at.desc())
        .limit(LIST_LIMIT)
    ).all()

    my_pending = session.scalar(
        select(func.count(IncidentAssignmentRequest.id)).where(
            IncidentAssignmentRequest.engineer_id == profile_id,
            IncidentAssignmentRequest.status == AssignmentRequestStatus.PENDING,
        )
    )

    open_to_request = session.scalar(
        select(func.count(Incident.id)).where(
            Incident.assignee_id.is_(None), Incident.status == IncidentStatus.OPEN
        )
    )

    return {
        "role": UserRole.ENGINEER.value,
        "counts_by_status": count_by(session, Incident.status, assigned),
        "counts_by_priority": count_by(session, Incident.priority, assigned),
        "active_count": active_count or 0,
        "assigned_incidents": [incident_summary(incident) for incident in active],
        "my_pending_requests": my_pending or 0,
        "open_to_request": open_to_request or 0,
        "avg_hours_to_resolve": average_hours(session, Incident.resolved_at, assigned),
        "needs_profile": False,
    }


# --- Facility admin ---------------------------------------------------------


def top_locations(session):
    """
    The buildings with the most incidents — the recurring-problem hotspots.

    Admin only: an employee with two tickets learns nothing from a league table
    of buildings, and it is not their question to ask.
    """
    statement = (
        select(Building.id, Building.name, func.count(Incident.id).label("total"))
        .join(Building, Incident.building_id == Building.id)
        .group_by(Building.id, Building.name)
        .order_by(func.count(Incident.id).desc())
        .limit(TOP_LOCATIONS_LIMIT)
    )

    return [
        {"building_id": str(building_id), "name": name, "count": total}
        for building_id, name, total in session.execute(statement).all()
    ]


def escalated_and_blocked(session):
    """
    Incidents that need an admin to act, and the reason given for each.

    The brief asks specifically which incidents are escalated or blocked and
    why, so the reason text is included rather than just a count.
    """
    incidents = session.scalars(
        select(Incident).where(
            (Incident.escalated.is_(True)) | (Incident.status == IncidentStatus.BLOCKED)
        )
    ).all()

    return [
        {
            "id": str(incident.id),
            "title": incident.title,
            "status": incident.status.value,
            "priority": incident.priority.value,
            "escalated": incident.escalated,
            "escalation_reason": incident.escalation_reason,
            "blocked_reason": incident.blocked_reason,
        }
        for incident in incidents
    ]


def workload(session):
    """
    How many incidents each engineer is carrying, by name.

    Named rather than keyed by id, for the same reason the assignment queue
    names people: an admin deciding who to give the next job to cannot act on
    "37b3d107 has three". Busiest first, because that is the end of the list
    worth looking at.
    """
    rows = session.execute(
        select(EngineerProfile.id, User.full_name, func.count(Incident.id))
        .select_from(Incident)
        .join(EngineerProfile, Incident.assignee_id == EngineerProfile.id)
        .join(User, EngineerProfile.user_id == User.id)
        .group_by(EngineerProfile.id, User.full_name)
        .order_by(func.count(Incident.id).desc())
    ).all()

    return [
        {"engineer_id": str(profile_id), "name": name, "count": total}
        for profile_id, name, total in rows
    ]


def engineer_availability(session):
    """
    How many engineers are available, busy, or off.

    Sits next to the workload figures on purpose: knowing one engineer is
    carrying nine incidents only helps if you also know who is free to take
    some of them.
    """
    rows = session.execute(
        select(EngineerProfile.availability, func.count(EngineerProfile.id))
        .group_by(EngineerProfile.availability)
    ).all()

    counts = {status.value: 0 for status in AvailabilityStatus}
    for availability, total in rows:
        counts[availability.value] = total
    return counts


def admin_summary(session):
    """Everything, for the person responsible for all of it."""
    everything = []

    pending_requests = session.scalar(
        select(func.count(IncidentAssignmentRequest.id)).where(
            IncidentAssignmentRequest.status == AssignmentRequestStatus.PENDING
        )
    )

    return {
        "role": UserRole.FACILITY_ADMIN.value,
        "counts_by_status": count_by(session, Incident.status, everything),
        "counts_by_priority": count_by(session, Incident.priority, everything),
        "workload": workload(session),
        # Only incidents still needing work. A closed incident with no assignee
        # is not "waiting for an owner" — nobody is ever going to pick it up.
        "unassigned_count": session.scalar(
            select(func.count(Incident.id)).where(
                Incident.assignee_id.is_(None), Incident.status.in_(ACTIVE_STATUSES)
            )
        ) or 0,
        "category_breakdown": count_by(session, Incident.category, everything),
        "avg_hours_to_acknowledge": average_hours(session, Incident.acknowledged_at, everything),
        "avg_hours_to_assign": average_hours(session, Incident.assigned_at, everything),
        "avg_hours_to_resolve": average_hours(session, Incident.resolved_at, everything),
        "top_locations": top_locations(session),
        "escalated_blocked": escalated_and_blocked(session),
        "engineer_availability": engineer_availability(session),
        "pending_assignment_requests": pending_requests or 0,
    }


def build_summary(session, user, profile_id):
    """
    Pick the right dashboard for whoever is asking.

    Args:
        profile_id: the caller's engineer profile id, or None. Passed in rather
            than looked up here so the route makes only one such query.
    """
    if user.role == UserRole.FACILITY_ADMIN:
        return admin_summary(session)

    if user.role == UserRole.ENGINEER:
        return engineer_summary(session, user, profile_id)

    return employee_summary(session, user)
