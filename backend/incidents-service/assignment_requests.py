"""
Filling in the details behind a list of assignment requests.

Part of: backend / incidents service.

Why its own file: a request row stores two ids — which engineer, which
incident — and nobody deciding on one wants to read ids. Looking each one up
while building the response would be a query per row, so the lookups happen
once for the whole list here, and the routes stay about routing.
"""

from sqlalchemy import select

from models import EngineerProfile, Incident, User
from schemas import AssignmentRequestOut, IncidentSummary


def describe(session, requests):
    """
    Turn request rows into responses that name the engineer and the incident.

    Two extra queries in total, whether the list has three rows or three
    hundred: one for the people, one for the incidents.

    Args:
        session: the database session for this request.
        requests (list[IncidentAssignmentRequest]): the rows to describe.

    Returns:
        list[AssignmentRequestOut]: the response bodies, in the order given.
    """
    if not requests:
        return []

    engineer_ids = {item.engineer_id for item in requests}
    incident_ids = {item.incident_id for item in requests}

    # The person behind each engineer profile, keyed by profile id.
    people_rows = session.execute(
        select(EngineerProfile.id, User)
        .join(User, EngineerProfile.user_id == User.id)
        .where(EngineerProfile.id.in_(engineer_ids))
    ).all()
    people = {profile_id: user for profile_id, user in people_rows}

    incidents = {
        incident.id: incident
        for incident in session.scalars(
            select(Incident).where(Incident.id.in_(incident_ids))
        ).all()
    }

    described = []
    for item in requests:
        payload = AssignmentRequestOut.model_validate(item)

        person = people.get(item.engineer_id)
        if person is not None:
            payload.engineer_name = person.full_name
            payload.engineer_email = person.email

        incident = incidents.get(item.incident_id)
        if incident is not None:
            payload.incident = IncidentSummary.model_validate(incident)

        described.append(payload)

    return described
