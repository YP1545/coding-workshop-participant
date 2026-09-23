"""
Registering, signing in, and what a token is worth.

Part of: backend / tests.

Why its own file: this is the security boundary. Most of the tests below are
about what must NOT work — a forged token, an expired one, a password that was
quietly trimmed — because those failures are silent. Nothing throws when a
check is missing; the request simply succeeds for the wrong person.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

PASSWORD = "TestPassw0rd!"


def unique_email(prefix="person"):
    """An address nothing else in the run will collide with."""
    return f"{prefix}{uuid.uuid4().hex[:8]}@acme.inc"


def test_registering_creates_an_employee(anonymous):
    """Everyone starts as an employee, whatever they ask for."""
    status, account = anonymous.post("users", "/auth/register", {
        "email": unique_email(), "password": PASSWORD, "full_name": "New Person"})

    assert status == 201
    assert account["role"] == "employee"


def test_a_role_cannot_be_chosen_at_registration(anonymous):
    """
    Sending a role is a 400, not a silently ignored field.

    Ignoring it would be safe but confusing; accepting it would let anyone sign
    up as an admin.
    """
    status, _ = anonymous.post("users", "/auth/register", {
        "email": unique_email(), "password": PASSWORD, "full_name": "Sneaky",
        "role": "facility_admin"})

    assert status == 400


def test_registration_requires_a_company_address(anonymous):
    status, _ = anonymous.post("users", "/auth/register", {
        "email": "outsider@gmail.com", "password": PASSWORD, "full_name": "Outsider"})

    assert status == 400


def test_registration_requires_a_long_enough_password(anonymous):
    status, _ = anonymous.post("users", "/auth/register", {
        "email": unique_email(), "password": "short", "full_name": "Short"})

    assert status == 400


def test_the_same_address_cannot_register_twice(anonymous):
    address = unique_email()
    anonymous.post("users", "/auth/register", {
        "email": address, "password": PASSWORD, "full_name": "First"})

    status, _ = anonymous.post("users", "/auth/register", {
        "email": address, "password": PASSWORD, "full_name": "Second"})

    assert status == 409


def test_a_password_with_spaces_still_works(anonymous):
    """
    A regression test.

    Registering hashed the password verbatim while signing in trimmed it, so an
    account created with surrounding spaces could never be signed into again —
    by anyone, including its owner.
    """
    address = unique_email("padded")
    padded = "  surrounded by spaces  "

    status, _ = anonymous.post("users", "/auth/register", {
        "email": address, "password": padded, "full_name": "Padded"})
    assert status == 201

    status, _ = anonymous.post("users", "/auth/login", {"email": address, "password": padded})
    assert status == 200

    status, _ = anonymous.post("users", "/auth/login", {
        "email": address, "password": padded.strip()})
    assert status == 401


def test_signing_in_is_case_insensitive_on_the_address(anonymous):
    address = unique_email("caps")
    anonymous.post("users", "/auth/register", {
        "email": address, "password": PASSWORD, "full_name": "Caps"})

    status, _ = anonymous.post("users", "/auth/login", {
        "email": address.upper(), "password": PASSWORD})

    assert status == 200


def test_a_wrong_password_and_an_unknown_address_look_identical(anonymous):
    """
    Otherwise the login endpoint tells an attacker which addresses have accounts.
    """
    address = unique_email("real")
    anonymous.post("users", "/auth/register", {
        "email": address, "password": PASSWORD, "full_name": "Real"})

    wrong_status, wrong = anonymous.post("users", "/auth/login", {
        "email": address, "password": "not-the-password"})
    unknown_status, unknown = anonymous.post("users", "/auth/login", {
        "email": unique_email("ghost"), "password": PASSWORD})

    assert wrong_status == unknown_status == 401
    assert wrong["detail"] == unknown["detail"]


def test_the_hash_is_never_returned(admin):
    """No response may carry password_hash, whatever the caller's role."""
    status, users = admin.get("users", "/users")

    assert status == 200
    assert all("password_hash" not in person for person in users)


@pytest.mark.parametrize("token,reason", [
    (None, "no token at all"),
    ("not-a-real-token", "a string that is not a token"),
])
def test_a_protected_route_needs_a_real_token(anonymous, token, reason):
    client = anonymous.as_token(token) if token else anonymous

    status, _ = client.get("users", "/auth/me")

    assert status == 401, reason


def test_an_expired_token_is_refused(anonymous, people):
    from auth import ALGORITHM, jwt_secret

    expired = jwt.encode(
        {"sub": people["employee_user"]["id"], "role": "employee",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        jwt_secret(), algorithm=ALGORITHM)

    status, _ = anonymous.as_token(expired).get("users", "/auth/me")

    assert status == 401


def test_a_token_signed_with_another_key_is_refused(anonymous, people):
    from auth import ALGORITHM

    forged = jwt.encode(
        {"sub": people["employee_user"]["id"], "role": "facility_admin",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "attacker-guessed-secret", algorithm=ALGORITHM)

    status, _ = anonymous.as_token(forged).get("users", "/auth/me")

    assert status == 401


def test_an_unsigned_token_is_refused(anonymous, people):
    """
    The alg=none attack.

    decode_token pins the algorithm to a single value; without that, a token
    claiming to need no signature would be accepted as valid.
    """
    unsigned = jwt.encode(
        {"sub": people["employee_user"]["id"], "role": "facility_admin"},
        None, algorithm="none")

    status, _ = anonymous.as_token(unsigned).get("users", "/auth/me")

    assert status == 401


def test_the_role_in_the_token_is_not_believed(anonymous, people):
    """
    The most important test in this file.

    The token is signed by us and says facility_admin, but the account behind it
    is an employee. The role must come from the database on every request, or a
    stolen-then-edited token is a free promotion.
    """
    from auth import ALGORITHM, jwt_secret

    lying = jwt.encode(
        {"sub": people["employee_user"]["id"], "role": "facility_admin",
         "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        jwt_secret(), algorithm=ALGORITHM)

    status, _ = anonymous.as_token(lying).get("users", "/users")

    assert status == 403


def test_the_signing_key_fails_closed_when_deployed(monkeypatch):
    """
    A deployed Lambda with no JWT_SECRET must refuse to issue tokens.

    infra/locals.tf injects no such variable, so falling back to a default would
    mean signing tokens with a string published in this repository.
    """
    import auth
    from errors import ApiError

    monkeypatch.setenv("JWT_SECRET", "")
    monkeypatch.setenv("IS_LOCAL", "false")

    with pytest.raises(ApiError) as raised:
        auth.jwt_secret()

    assert raised.value.status == 500
