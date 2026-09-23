"""
Users service: registration, sign-in, tokens, and role management.

Part of: backend / users service (one Lambda).

Why its own service: this is the identity boundary. It is the only service that
reads a password hash or issues a token, so the code worth attacking lives in
one small file that can be reviewed on its own.

Every route below declares who may call it in its own signature — see deps.py.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import create_app, lambda_handler
from auth import create_access_token, hash_password, verify_password, waste_time_like_a_real_check
from crud import get_or_404, save
from deps import ADMIN_ONLY, get_current_user, get_session, require_roles
from errors import ApiError
from models import EngineerProfile, User, UserRole
from schemas import LoginIn, RegisterIn, RoleIn, TokenOut, UserOut

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_NAME = "users-service"

app = create_app(SERVICE_NAME, "ACME Facility Incidents — users and identity")
router = APIRouter()


@router.post("/auth/register", response_model=UserOut, status_code=201, tags=["auth"])
def register(payload: RegisterIn, session: Session = Depends(get_session)):
    """
    Self-service registration, restricted to @acme.inc addresses.

    Everyone registers as an employee. The request model has no role field at
    all, so there is nothing to ignore or forget to ignore.
    """
    account = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.EMPLOYEE,
    )
    session.add(account)
    save(session, account, conflict="An account with that email already exists")
    logger.info("Registered new account %s", account.id)
    return account


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(payload: LoginIn, session: Session = Depends(get_session)):
    """
    Exchange credentials for a bearer token.

    An unknown address and a wrong password return the same message after the
    same amount of work, so the endpoint cannot be used to discover which
    addresses have accounts.
    """
    email = payload.email.strip().lower()
    account = session.scalar(select(User).where(func.lower(User.email) == email))

    if account is None:
        waste_time_like_a_real_check()
        logger.info("Failed login for unknown address")
        raise ApiError(401, "Invalid email or password")

    if not verify_password(payload.password, account.password_hash):
        logger.info("Failed login for account %s", account.id)
        raise ApiError(401, "Invalid email or password")

    return {
        "access_token": create_access_token(account),
        "token_type": "bearer",
        "user": account,
    }


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(get_current_user)):
    """Return the caller's own account, as loaded from the database this request."""
    return user


@router.get("/users", response_model=list[UserOut], tags=["users"])
def list_users(
    role: UserRole | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """List accounts, optionally filtered by role. Admin only: this is the staff directory."""
    statement = select(User)
    if role is not None:
        statement = statement.where(User.role == role)
    return session.scalars(
        statement.order_by(User.full_name).limit(limit).offset(offset)
    ).all()


@router.get("/users/{user_id}", response_model=UserOut, tags=["users"])
def get_user(
    user_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Fetch one account. Callers wanting their own should use /auth/me."""
    return get_or_404(session, User, user_id, "User")


@router.patch("/users/{user_id}/role", response_model=UserOut, tags=["users"])
def update_user_role(
    user_id: uuid.UUID,
    payload: RoleIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Change a user's role, and keep the engineer rota in step with it.

    Promoting somebody to engineer also creates their engineer profile, because
    incidents are assigned to a profile rather than to an account — without one
    they would hold the role but be unable to receive any work.

    Demoting them does NOT delete that profile. Incidents point at it with
    ON DELETE SET NULL, so deleting it would erase the record of who fixed every
    incident they ever closed. The profile stays; the roster lists only people
    whose role is currently engineer, and re-promoting restores the specialty
    they had before.

    An admin cannot change their own role, or the last one could demote
    themselves and leave nobody able to manage the site.
    """
    if user_id == user.id:
        raise ApiError(403, "You cannot change your own role")

    account = get_or_404(session, User, user_id, "User")
    account.role = payload.role

    if account.role == UserRole.ENGINEER:
        existing = session.scalar(
            select(EngineerProfile).where(EngineerProfile.user_id == account.id)
        )
        if existing is None:
            session.add(EngineerProfile(user_id=account.id))

    save(session, account)
    logger.info("Role of account %s changed to %s by %s", account.id, account.role.value, user.id)
    return account


app.include_router(router)

# The entry point AWS calls. infra/locals.tf sets the handler to
# "function.handler", so the name matters.
handler = lambda_handler(app, SERVICE_NAME)
