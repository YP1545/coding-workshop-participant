"""
Who is allowed to see which incidents.

Part of: backend / incidents service (access rules).

Why its own file: two different places need these rules — the list endpoint and
the dashboard — and a rule that is written twice is a rule that will disagree
with itself eventually. Keeping them here means there is one answer to "what
can this person see", and both callers get it.
"""

from sqlalchemy import case, false, or_, select

from models import EngineerProfile, Incident, IncidentStatus, UserRole
from errors import ApiError


def engineer_profile_id(session, user):
    """
    The caller's engineer profile id, or None if they do not have one.

    Incidents are assigned to a profile rather than to a user account, so any
    check about "my incidents" has to look this up first. An account can hold
    the engineer role without a profile row, if an admin promoted it but has
    not finished setting it up.
    """
    if user.role != UserRole.ENGINEER:
        return None

    return session.scalar(
        select(EngineerProfile.id).where(EngineerProfile.user_id == user.id)
    )


def order_for(user, statement, profile_id):
    """
    Decide the order of an incident list.

    An engineer opens this page to see what they have to do today, so their own
    assigned work comes first, then everything else, newest first within each
    group. Everyone else just gets newest first.

    The CASE reads like an if/else: 0 for mine, 1 for anything else — including
    unassigned incidents, where the comparison would otherwise be NULL.
    """
    if user.role == UserRole.ENGINEER and profile_id is not None:
        mine_first = case((Incident.assignee_id == profile_id, 0), else_=1)
        return statement.order_by(mine_first, Incident.created_at.desc())

    return statement.order_by(Incident.created_at.desc())


def scope_for(session, user, statement):
    """
    Add a WHERE clause limiting a query to the incidents this person may see.

    The rules:
      * a facility admin sees everything
      * an engineer sees what is assigned to them, plus unassigned open
        incidents they could pick up
      * everyone else sees the incidents they reported

    This is done in SQL rather than by filtering a list afterwards. Filtering
    in Python would still pull other people's rows out of the database, and one
    forgotten filter would then hand them to the wrong person.
    """
    if user.role == UserRole.FACILITY_ADMIN:
        return statement

    if user.role == UserRole.ENGINEER:
        profile_id = engineer_profile_id(session, user)

        # Careful: comparing a column to None produces "IS NULL" in SQL, which
        # would match every unassigned incident instead of none of them. When
        # there is no profile, this half of the condition must simply be false.
        if profile_id is None:
            assigned_to_me = false()
        else:
            assigned_to_me = Incident.assignee_id == profile_id

        unassigned_and_open = (Incident.assignee_id.is_(None)) & (
            Incident.status == IncidentStatus.OPEN
        )
        return statement.where(or_(assigned_to_me, unassigned_and_open))

    return statement.where(Incident.reporter_id == user.id)


def can_comment_on(session, user, incident):
    """
    True if this person may add a note to this incident.

    Seeing an incident and having something to say about it are different
    things. An engineer browsing unassigned work can read it to decide whether
    to ask for it, but the thread belongs to the people actually involved: the
    person who reported it, the engineer it was given to, and the admins.
    Otherwise any engineer could comment on every open job in the building.
    """
    if user.role == UserRole.FACILITY_ADMIN:
        return True

    if incident.reporter_id == user.id:
        return True

    if user.role == UserRole.ENGINEER and incident.assignee_id is not None:
        return incident.assignee_id == engineer_profile_id(session, user)

    return False


def visible_incident(session, user, incident_id):
    """
    Load an incident this person is allowed to see, or raise 404.

    Note it raises 404 rather than 403 when the incident exists but is not
    theirs. A 403 would confirm that an incident with that id exists, which is
    something an outsider should not be able to find out by guessing.
    """
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise ApiError(404, "Incident not found")

    if user.role == UserRole.FACILITY_ADMIN:
        return incident

    if incident.reporter_id == user.id:
        return incident

    if user.role == UserRole.ENGINEER:
        profile_id = engineer_profile_id(session, user)

        if incident.assignee_id is not None and incident.assignee_id == profile_id:
            return incident

        if incident.assignee_id is None and incident.status == IncidentStatus.OPEN:
            return incident

    raise ApiError(404, "Incident not found")
