"""
Engineers service: the rota and availability.

Part of: backend / engineers service (one Lambda).

Why its own service: engineer profiles are written by admins and read by the
assignment flow, a different access pattern from either identity or incidents.

Access rule: admins manage the roster; any signed-in person may read it,
because the incident screens show who a ticket is assigned to. The one
exception is an engineer updating their own availability, checked inside the
handler because it depends on which profile is being touched.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import create_app, lambda_handler
from crud import delete, get_or_404, save
from deps import ADMIN_ONLY, ADMIN_OR_ENGINEER, get_current_user, get_session, require_roles
from errors import ApiError
from models import AvailabilityStatus, EngineerProfile, User, UserRole
from schemas import EngineerIn, EngineerOut, EngineerUpdateIn

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_NAME = "engineers-service"

# Stored in password_hash when an admin provisions an engineer account without a
# password. bcrypt can never produce this value, so every check against it
# fails: the account exists and can be assigned work, but cannot be signed into
# until there is a set-password flow. Safer than generating a real password that
# would then have to be transmitted somehow.
LOCKED_PASSWORD_HASH = "!"

# What an engineer may change on their own profile. Specialty is deliberately
# absent: what somebody is qualified for is a management decision.
ENGINEER_SELF_EDITABLE = {"availability"}

app = create_app(SERVICE_NAME, "ACME Facility Incidents — engineer profiles")
router = APIRouter()


def with_person(profile, account):
    """
    Build the response shape, folding in the person's name and email.

    The engineer table and every assignee dropdown need a human label, so it is
    included here rather than costing the frontend a request per row.
    """
    payload = EngineerOut.model_validate(profile)
    if account is not None:
        payload.full_name = account.full_name
        payload.email = account.email
    return payload


@router.post("/engineers", response_model=EngineerOut, status_code=201, tags=["engineers"])
def create_engineer(
    payload: EngineerIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Add somebody to the rota, two ways.

    Either promote an existing account with user_id, or provision a new one with
    email and full_name. Both set the account's role to engineer, so the role
    and the profile can never disagree.
    """
    has_new_account_fields = payload.email is not None or payload.full_name is not None

    if payload.user_id and has_new_account_fields:
        raise ApiError(400, "Provide either 'user_id' or 'email' and 'full_name', not both")
    if not payload.user_id and not (payload.email and payload.full_name):
        raise ApiError(400, "Provide 'user_id', or both 'email' and 'full_name'")

    if payload.user_id:
        account = get_or_404(session, User, payload.user_id, "User")
        existing = session.scalar(
            select(EngineerProfile).where(EngineerProfile.user_id == account.id)
        )
        if existing is not None:
            raise ApiError(409, "That user already has an engineer profile")
    else:
        account = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=LOCKED_PASSWORD_HASH,
            role=UserRole.ENGINEER,
        )
        session.add(account)
        save(session, account, conflict="An account with that email already exists")

    account.role = UserRole.ENGINEER
    profile = EngineerProfile(
        user_id=account.id,
        specialty=payload.specialty,
        availability=payload.availability,
    )
    session.add(profile)
    save(session, profile, conflict="That user already has an engineer profile")
    logger.info("Engineer profile %s created by %s", profile.id, user.id)
    return with_person(profile, account)


@router.get("/engineers", response_model=list[EngineerOut], tags=["engineers"])
def list_engineers(
    availability: AvailabilityStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    List the rota, optionally filtered by availability.

    Only people who currently hold the engineer role. A profile outlives a
    demotion on purpose — it carries the record of what they worked on — but
    somebody who is an employee again should not appear here or in an
    assignment dropdown.

    Users are joined in one statement rather than lazy-loaded per profile,
    which would be a query per row on a page that always shows names.
    """
    statement = (
        select(EngineerProfile, User)
        .join(User, EngineerProfile.user_id == User.id)
        .where(User.role == UserRole.ENGINEER)
    )
    if availability is not None:
        statement = statement.where(EngineerProfile.availability == availability)

    rows = session.execute(
        statement.order_by(User.full_name).limit(limit).offset(offset)
    ).all()
    return [with_person(profile, account) for profile, account in rows]


@router.get("/engineers/{engineer_id}", response_model=EngineerOut, tags=["engineers"])
def get_engineer(
    engineer_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Fetch one engineer profile with the person's name and email."""
    profile = get_or_404(session, EngineerProfile, engineer_id, "Engineer profile")
    return with_person(profile, session.get(User, profile.user_id))


@router.put("/engineers/{engineer_id}", response_model=EngineerOut, tags=["engineers"])
def update_engineer(
    engineer_id: uuid.UUID,
    payload: EngineerUpdateIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_OR_ENGINEER)),
):
    """
    Update specialty and availability.

    An admin may change either field on any profile. An engineer may change only
    their own availability — checked against the profile's user_id rather than a
    claim in the token, so one engineer cannot mark another unavailable to
    divert work away from themselves.
    """
    profile = get_or_404(session, EngineerProfile, engineer_id, "Engineer profile")

    if user.role != UserRole.FACILITY_ADMIN:
        if profile.user_id != user.id:
            raise ApiError(403, "You can only update your own profile")
        forbidden = payload.model_fields_set - ENGINEER_SELF_EDITABLE
        if forbidden:
            raise ApiError(403, f"You can only update: {', '.join(sorted(ENGINEER_SELF_EDITABLE))}")

    if "specialty" in payload.model_fields_set:
        profile.specialty = payload.specialty
    if payload.availability is not None:
        profile.availability = payload.availability

    save(session, profile)
    return with_person(profile, session.get(User, profile.user_id))


@router.delete("/engineers/{engineer_id}", status_code=204, tags=["engineers"])
def delete_engineer(
    engineer_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Delete an engineer profile outright.

    Rarely the right tool: incidents point at the profile with ON DELETE SET
    NULL, so this blanks the assignee on everything that person ever worked.
    Taking somebody off the rota should normally be a role change instead, which
    keeps that history — see PATCH /users/{id}/role.
    """
    profile = get_or_404(session, EngineerProfile, engineer_id, "Engineer profile")
    delete(session, profile, "Engineer profile")
    logger.info("Engineer profile %s deleted by %s", engineer_id, user.id)


app.include_router(router)

handler = lambda_handler(app, SERVICE_NAME)
