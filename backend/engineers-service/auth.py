"""
Password hashing, JWT issuing and verification.

Part of: backend / core (security).

Why its own file: this is the only module that touches password hashes and the
signing key. Keeping it separate from routing and data access means the code an
attacker cares about most can be read end to end in one sitting, and a change
to it is obvious in review.

This file is the canonical copy. Do not edit the copies inside the service
directories — edit here and run ./sync.sh.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from db import is_local
from errors import ApiError

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24

# bcrypt hashes at most 72 bytes and silently ignores the rest, so two
# passwords sharing a 72-byte prefix would be interchangeable. The API rejects
# anything longer instead of truncating it.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8

# Used only when IS_LOCAL is true. Deployed environments must supply
# JWT_SECRET — see jwt_secret().
LOCAL_DEV_SECRET = "local-development-only-not-a-real-secret"

# A real bcrypt hash of a random value, compared against when an email is not
# found. Without it, a failed login returns noticeably faster for an unknown
# address than for a known one, which turns the login endpoint into an account
# enumeration oracle.
_DUMMY_HASH = bcrypt.hashpw(uuid.uuid4().hex.encode(), bcrypt.gensalt())


def jwt_secret() -> str:
    """
    Return the token signing key.

    Fails closed off the developer's machine. infra/locals.tf injects no
    JWT_SECRET, so a deployed Lambda would otherwise fall back to a default
    that is published in this repository — and anyone who read it could mint a
    facility_admin token. Raising here turns that silent compromise into a loud
    500 on the first request.
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    if is_local():
        return LOCAL_DEV_SECRET
    raise ApiError(500, "Server is not configured for authentication")


def hash_password(plaintext: str) -> str:
    """Hash a password with a per-hash salt."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    """
    Check a password against a stored hash.

    Returns False rather than raising on a malformed or sentinel hash: accounts
    provisioned by an admin store "!" in password_hash, which is not valid
    bcrypt output, and those accounts must simply fail to authenticate.
    """
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def waste_time_like_a_real_check() -> None:
    """Spend the same time a real password check would, for unknown emails."""
    bcrypt.checkpw(b"not-the-password", _DUMMY_HASH)


def create_access_token(user) -> str:
    """
    Issue a signed token for a user.

    The role is included so the frontend can render the right navigation
    immediately, but the backend never trusts it — authenticate() reloads the
    user from the database on every request, so a role change or a deleted
    account takes effect at once instead of when the token happens to expire.
    """
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": issued_at,
        "exp": issued_at + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Verify a token's signature and expiry, returning its claims.

    algorithms is pinned to a single value: accepting a list the caller can
    influence is how the "alg: none" and RS256-to-HS256 confusion attacks work.
    """
    try:
        return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "Token has expired")
    except jwt.InvalidTokenError:
        raise ApiError(401, "Invalid token")


def bearer_token(headers) -> str:
    """
    Pull the token out of an Authorization header.

    Args:
        headers: request headers, lowercased keys.

    Raises:
        ApiError: 401 when the header is missing or not a Bearer credential.
    """
    header = headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "Authentication required")
    return token.strip()
