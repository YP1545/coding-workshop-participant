"""
The dependencies every protected endpoint declares.

Part of: backend / api (request pipeline).

Why its own file: authentication, the database session and the role check are
the same three questions on nearly every endpoint, and the dangerous failure is
forgetting one. As FastAPI dependencies they are declared in the signature,
where they are visible in the route definition itself:

    def create_building(..., user: User = Depends(require_roles(ADMIN))):

A route that needs a role says so in its own signature. There is no way to
"forget" it and still have the endpoint compile into something that looks
finished.

This file is the canonical copy. Do not edit the copies inside the service
directories — edit here and run ./sync.sh.
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import bearer_token, decode_token
from db import session_scope
from errors import ApiError
from models import User, UserRole

# Role groups, named so a route reads as a sentence.
ANY_ROLE = tuple(UserRole)
ADMIN_ONLY = (UserRole.FACILITY_ADMIN,)
ENGINEER_ONLY = (UserRole.ENGINEER,)
ADMIN_OR_ENGINEER = (UserRole.FACILITY_ADMIN, UserRole.ENGINEER)

# auto_error is off so a missing header raises our own 401 with the API's
# error shape, rather than FastAPI's default body.
bearer_scheme = HTTPBearer(auto_error=False)


def get_session():
    """
    Yield a database session for one request.

    The session commits when the endpoint returns and rolls back if it raises,
    so a failed request can never leave a half-applied transaction behind on a
    connection the next invocation will reuse.
    """
    with session_scope() as session:
        yield session


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session=Depends(get_session),
) -> User:
    """
    Resolve the caller from the Authorization header.

    The user is loaded from the database rather than trusted from the token's
    claims. A token is signed by us and cannot be edited, but it was issued up
    to 24 hours ago — reloading means a role change or a deleted account takes
    effect on the next request instead of whenever the token expires.

    Raises:
        ApiError: 401 when the token is missing, malformed, expired, or names a
            user that no longer exists.
    """
    if credentials is None:
        raise ApiError(401, "Authentication required")

    claims = decode_token(credentials.credentials)

    try:
        user_id = uuid.UUID(claims.get("sub", ""))
    except (ValueError, AttributeError, TypeError):
        raise ApiError(401, "Invalid token")

    user = session.get(User, user_id)
    if user is None:
        raise ApiError(401, "Invalid token")
    return user


def require_roles(*roles):
    """
    Build a dependency that admits only the given roles.

    Args:
        *roles: UserRole members. Pass ANY_ROLE for "any signed-in person".

    Returns:
        A dependency returning the caller, or raising 403.
    """
    allowed = roles[0] if len(roles) == 1 and isinstance(roles[0], tuple) else roles

    def check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            # Deliberately vague: naming the required role tells somebody
            # probing the API which account to go after next.
            raise ApiError(403, "You do not have access to this resource")
        return user

    return check


# The common cases, so routes do not repeat the call.
CurrentUser = Depends(get_current_user)
AdminUser = Depends(require_roles(ADMIN_ONLY))
EngineerUser = Depends(require_roles(ENGINEER_ONLY))
DbSession = Depends(get_session)
