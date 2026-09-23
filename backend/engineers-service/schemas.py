"""
The shapes of every request and response.

Part of: backend / api (the contract).

Why its own file: with FastAPI these models *are* the API contract. They
validate what comes in, they decide what goes out, and they generate the
documentation — so the three can no longer disagree with each other.

Two rules worth stating, because they are load-bearing:

  * Request models set extra="forbid". An unknown field is a 400 rather than a
    silent no-op, which is what stops a client sending reporter_id or status
    and having it quietly ignored.
  * Response models are allow-lists. A field that is not declared here cannot
    be returned, which is why users.password_hash cannot leak no matter what a
    handler passes in.

This file is the canonical copy. Do not edit the copies inside the service
directories — edit here and run ./sync.sh.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from models import (
    AssignmentRequestStatus,
    AvailabilityStatus,
    IncidentPriority,
    IncidentStatus,
    UserRole,
)

# Registration is restricted to company addresses. Checked here for a clear 400,
# and again by the users.email CHECK constraint so no code path can bypass it.
ACME_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@acme\.inc$")

# bcrypt ignores everything past 72 bytes, so a longer password would be
# silently truncated — two passwords sharing a prefix would both work.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

MAX_NAME = 200
MAX_BODY = 5000


def to_utc(value: datetime) -> datetime:
    """
    Normalise a timestamp to UTC before it is serialised.

    A value just written comes back from Python as +00:00 while one reloaded
    from PostgreSQL arrives in the server's local offset. They are the same
    instant, printed two ways, and a client sorting them as text would get it
    wrong.
    """
    return value.astimezone(timezone.utc) if value is not None else value


# A datetime that always leaves as UTC.
Utc = Annotated[datetime, PlainSerializer(to_utc, return_type=datetime)]

# Free text with a length bound. Unbounded input is how a single request pushes
# megabytes into a TEXT column.
Name = Annotated[str, Field(min_length=1, max_length=MAX_NAME)]
# A category slug. Bounded and pattern-checked here so a megabyte of text
# never reaches the database lookup; whether the value exists is the
# handler's question.
Slug = Annotated[str, Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")]
Body = Annotated[str, Field(min_length=1, max_length=MAX_BODY)]


class Incoming(BaseModel):
    """
    Base for every request body.

    extra="forbid" makes an unexpected field a 400. Silently ignoring one hides
    typos — a client sending "priorty" would otherwise get a 200 and wonder why
    nothing changed — and it is what stops a caller setting a field the
    endpoint never meant to expose.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(BaseModel):
    """
    Base for anything carrying a password.

    Deliberately does NOT strip whitespace. Incoming does, which is right for a
    title or a name, but a password is a secret: trimming it at registration and
    not at login (or the reverse) locks somebody out of an account they created
    with a leading space, permanently and for everyone including themselves.
    Fields that should be trimmed here do it explicitly in a validator.
    """

    model_config = ConfigDict(extra="forbid")


class Outgoing(BaseModel):
    """Base for every response body, read from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


# --- Auth and users ---------------------------------------------------------


class RegisterIn(Credentials):
    """
    A new account.

    There is deliberately no role field. Everyone registers as an employee and
    only a facility admin can promote them; accepting a role here would let
    anyone sign up as an admin.
    """

    email: str
    password: str
    full_name: Name

    @field_validator("email")
    @classmethod
    def must_be_a_company_address(cls, value: str) -> str:
        """Trim, lowercase, and check the domain. The unique index is on lower(email)."""
        value = value.strip().lower()
        if not ACME_EMAIL_PATTERN.match(value):
            raise ValueError("must be a valid @acme.inc address")
        return value

    @field_validator("full_name")
    @classmethod
    def tidy_the_name(cls, value: str) -> str:
        """Trimmed explicitly, since this model does not strip everything."""
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("password")
    @classmethod
    def long_enough_but_not_too_long(cls, value: str) -> str:
        """
        Bounds checked before the value reaches bcrypt.

        Not trimmed: leading and trailing spaces are legitimate password
        characters, and stripping them would lock somebody out of an account
        they created with them.
        """
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class LoginIn(Credentials):
    """
    Credentials being checked.

    Neither field is policy-checked here. Applying the length rule would answer
    400 instead of 401 — telling somebody their guess was rejected on shape
    rather than on being wrong.
    """

    email: str
    password: str


class RoleIn(Incoming):
    """A role change, on its own endpoint because it is a privilege change."""

    role: UserRole


class UserOut(Outgoing):
    """
    The public shape of a person.

    password_hash is absent, and because this is an allow-list it cannot be
    added by accident from a handler.
    """

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    created_at: Utc
    updated_at: Utc


class TokenOut(Outgoing):
    """What a successful sign-in returns."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Facilities -------------------------------------------------------------


class BuildingIn(Incoming):
    """
    A building.

    address is optional and omitting it on an update leaves it unchanged;
    sending null clears it. Treating "absent" as "clear it" silently destroys
    data when a form sends only the fields somebody edited.
    """

    name: Name
    address: str | None = Field(default=None, max_length=MAX_NAME)


class BuildingOut(Outgoing):
    id: uuid.UUID
    name: str
    address: str | None
    created_at: Utc
    updated_at: Utc


class FloorIn(Incoming):
    name: Name


class FloorOut(Outgoing):
    id: uuid.UUID
    building_id: uuid.UUID
    name: str
    created_at: Utc
    updated_at: Utc


class SeatIn(Incoming):
    label: Name


class SeatOut(Outgoing):
    id: uuid.UUID
    floor_id: uuid.UUID
    label: str
    created_at: Utc
    updated_at: Utc


# --- Engineers --------------------------------------------------------------


class EngineerIn(Incoming):
    """
    Adding somebody to the rota.

    Either promote an existing account with user_id, or provision a new one with
    email and full_name. The endpoint rejects both together.
    """

    user_id: uuid.UUID | None = None
    email: str | None = None
    full_name: Name | None = None
    specialty: str | None = Field(default=None, max_length=MAX_NAME)
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE

    @field_validator("email")
    @classmethod
    def must_be_a_company_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.lower()
        if not ACME_EMAIL_PATTERN.match(value):
            raise ValueError("must be a valid @acme.inc address")
        return value


class EngineerUpdateIn(Incoming):
    """
    Both fields optional, so an engineer flipping their availability does not
    have to resend their specialty — and so the server can tell the difference
    between "leave it" and "clear it".
    """

    specialty: str | None = Field(default=None, max_length=MAX_NAME)
    availability: AvailabilityStatus | None = None


class EngineerOut(Outgoing):
    """An engineer profile, with the person's name folded in."""

    id: uuid.UUID
    user_id: uuid.UUID
    specialty: str | None
    availability: AvailabilityStatus
    created_at: Utc
    updated_at: Utc
    full_name: str | None = None
    email: str | None = None


# --- Categories -------------------------------------------------------------


class CategoryOut(Outgoing):
    """
    One row of the category list.

    Returned so the frontend builds its dropdown from the database rather than
    a hardcoded array — otherwise adding a category by INSERT would make it
    filterable but not selectable.
    """

    slug: str
    name: str
    sort_order: int


# --- Incidents --------------------------------------------------------------


class IncidentIn(Incoming):
    """
    A reported incident.

    Note what is absent: reporter_id, status, assignee_id and the escalation
    flags. The reporter is the authenticated caller, the status always starts at
    open, and the rest have their own endpoints that enforce the rules. Sending
    any of them is a 400 rather than a quietly ignored field.
    """

    title: Name
    description: Body
    # Validated against incident_categories by the handler, not here: the
    # allowed values live in the database now, and Pydantic cannot query it.
    category: Slug = "other"
    priority: IncidentPriority = IncidentPriority.MEDIUM
    building_id: uuid.UUID | None = None
    floor_id: uuid.UUID | None = None
    seat_id: uuid.UUID | None = None


class IncidentUpdateIn(Incoming):
    """
    Editing the description of an incident.

    Title and description are required; everything else is left unchanged when
    omitted. model_fields_set is what lets the handler tell an omitted field
    from an explicit null.
    """

    title: Name
    description: Body
    category: Slug | None = None
    priority: IncidentPriority | None = None
    building_id: uuid.UUID | None = None
    floor_id: uuid.UUID | None = None
    seat_id: uuid.UUID | None = None


class StatusIn(Incoming):
    """A move through the workflow. The reason is required when blocking."""

    status: IncidentStatus
    blocked_reason: str | None = Field(default=None, max_length=MAX_BODY)


class AssignIn(Incoming):
    """Assign to an engineer profile, or send null to unassign."""

    assignee_id: uuid.UUID | None = None


class EscalateIn(Incoming):
    """
    Escalation, split by role: a reporter may request, only an admin may
    confirm. Both are optional so each caller sends only their own half.
    """

    escalation_requested: bool | None = None
    escalated: bool | None = None
    escalation_reason: str | None = Field(default=None, max_length=MAX_BODY)


class IncidentOut(Outgoing):
    """
    A full incident.

    Every lifecycle timestamp is declared even while null: the workflow stepper
    renders from them, and a missing key is harder to handle than an explicit
    null.
    """

    id: uuid.UUID
    # The database generates this; there is deliberately no matching field on
    # any Incoming model, so a client cannot choose or change its own number.
    reference: str
    title: str
    description: str
    category: str
    status: IncidentStatus
    priority: IncidentPriority
    building_id: uuid.UUID | None
    floor_id: uuid.UUID | None
    seat_id: uuid.UUID | None
    reporter_id: uuid.UUID
    assignee_id: uuid.UUID | None
    escalation_requested: bool
    escalated: bool
    escalation_reason: str | None
    blocked_reason: str | None
    acknowledged_at: Utc | None
    assigned_at: Utc | None
    resolved_at: Utc | None
    closed_at: Utc | None
    created_at: Utc
    updated_at: Utc


class IncidentPage(BaseModel):
    """
    One page of incidents.

    total is how many match the filters, not how many are on this page — it is
    what lets the frontend say "page 2 of 5". It travels in the body because the
    Function URLs set expose_headers = [] (infra/lambda.tf), so a browser could
    not read a custom header even if we sent one.
    """

    items: list[IncidentOut]
    total: int
    limit: int
    offset: int


class NoteIn(Incoming):
    """A note. The author is the caller, never a request field."""

    body: Body


class NoteOut(Outgoing):
    id: uuid.UUID
    incident_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: Utc


# --- Assignment requests ----------------------------------------------------


class DecisionIn(Incoming):
    """An admin approving or denying a request."""

    status: AssignmentRequestStatus


class IncidentSummary(Outgoing):
    """Enough of an incident to decide on a request without opening it."""

    id: uuid.UUID
    reference: str
    title: str
    description: str
    status: IncidentStatus
    priority: IncidentPriority
    category: str
    created_at: Utc


class AssignmentRequestOut(Outgoing):
    """
    An engineer asking for a job.

    The engineer's name and the incident are folded in because an admin
    choosing between two requests needs to see who is asking and what the work
    is. An id tells them neither.
    """

    id: uuid.UUID
    incident_id: uuid.UUID
    engineer_id: uuid.UUID
    status: AssignmentRequestStatus
    requested_at: Utc
    decided_at: Utc | None
    decided_by: uuid.UUID | None
    engineer_name: str | None = None
    engineer_email: str | None = None
    incident: IncidentSummary | None = None


# --- Dashboard --------------------------------------------------------------

# The dashboard returns a different shape per persona — an employee is not sent
# site-wide figures at all — so it is typed as a plain mapping rather than one
# model pretending to cover three. dashboard.py is where the shapes are built.
DashboardSummary = dict[str, Any]
