"""
Seed the local database with demo data for the three personas.

Part of: backend / migrations (developer tooling).

Why its own file: every later step needs believable data to work against —
Step 3 needs rows to list, Step 5 needs closed incidents with realistic
timestamps for the dashboard's timing metrics, Step 6 needs enough incidents
for filters to mean anything. Generating it from one script keeps demos
reproducible and lets the Step 7 tests assert against known numbers.

Never deployed: this file lives in _shared, which ships no Lambda.

Usage (from backend/_shared, with the repo venv active):
    python seed.py            # insert demo data, refuse if data already exists
    python seed.py --reset    # delete all rows first, then insert
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import delete, select

from db import is_local, session_scope
from models import (
    AvailabilityStatus,
    Building,
    EngineerProfile,
    Floor,
    Incident,
    IncidentAssignmentRequest,
    IncidentNote,
    IncidentPriority,
    IncidentStatus,
    IncidentStatusHistory,
    Seat,
    User,
    UserRole,
)

# Every seeded account shares this password. It is a local-development
# convenience, which is why the script refuses to run outside a local
# environment — see main(). Override with SEED_PASSWORD if you prefer.
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "LocalDev!2026")

# Tables in dependency order — children before parents, so --reset never trips
# a foreign key.
DELETE_ORDER = (
    IncidentAssignmentRequest,
    IncidentStatusHistory,
    IncidentNote,
    Incident,
    Seat,
    Floor,
    Building,
    EngineerProfile,
    User,
)


def hash_password(plaintext: str) -> str:
    """
    Hash a password the same way the auth service will in Step 4.

    bcrypt truncates silently past 72 bytes, so the API will also cap password
    length at validation time rather than letting a long password be quietly
    shortened here.
    """
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def ago(**delta) -> datetime:
    """Return a timezone-aware timestamp in the past, e.g. ago(hours=6)."""
    return datetime.now(timezone.utc) - timedelta(**delta)


def backdate(incidents) -> None:
    """
    Align updated_at with each incident's real last activity.

    Without this, every seeded incident carries created_at from days ago but
    updated_at of now(), which makes "recently updated" sorting in Step 6 show
    a ten-day-old closed ticket as the freshest thing in the list.
    """
    for incident in incidents:
        incident.updated_at = (
            incident.closed_at
            or incident.resolved_at
            or incident.assigned_at
            or incident.created_at
        )


def clear_all(session) -> None:
    """Delete every row, children first. Used by --reset."""
    for model in DELETE_ORDER:
        session.execute(delete(model))


def seed(session) -> dict:
    """
    Insert the demo dataset.

    Returns:
        dict: counts per entity, printed as a summary so a run is verifiable
            at a glance.
    """
    password_hash = hash_password(SEED_PASSWORD)

    # --- People -------------------------------------------------------------
    # Emails are stored lowercase: the unique index on lower(email) makes a
    # case-variant a duplicate, so normalizing on write is the only safe habit.
    admin = User(
        email="dana.admin@acme.inc",
        password_hash=password_hash,
        full_name="Dana Okafor",
        role=UserRole.FACILITY_ADMIN,
    )
    employee_one = User(
        email="sam.employee@acme.inc",
        password_hash=password_hash,
        full_name="Sam Rivera",
        role=UserRole.EMPLOYEE,
    )
    employee_two = User(
        email="priya.employee@acme.inc",
        password_hash=password_hash,
        full_name="Priya Nair",
        role=UserRole.EMPLOYEE,
    )
    engineer_user_one = User(
        email="alex.engineer@acme.inc",
        password_hash=password_hash,
        full_name="Alex Chen",
        role=UserRole.ENGINEER,
    )
    engineer_user_two = User(
        email="jo.engineer@acme.inc",
        password_hash=password_hash,
        full_name="Jo Bakker",
        role=UserRole.ENGINEER,
    )
    session.add_all([admin, employee_one, employee_two, engineer_user_one, engineer_user_two])
    session.flush()  # assign ids without ending the transaction

    engineer_one = EngineerProfile(
        user_id=engineer_user_one.id, specialty="HVAC and electrical", availability=AvailabilityStatus.AVAILABLE
    )
    engineer_two = EngineerProfile(
        user_id=engineer_user_two.id, specialty="Network and hardware", availability=AvailabilityStatus.BUSY
    )
    session.add_all([engineer_one, engineer_two])

    # --- Facilities ---------------------------------------------------------
    hq = Building(name="HQ Tower", address="1 Innovation Way")
    annex = Building(name="Riverside Annex", address="18 Mill Street")
    session.add_all([hq, annex])
    session.flush()

    floors = [
        Floor(building_id=hq.id, name="Level 1"),
        Floor(building_id=hq.id, name="Level 2"),
        Floor(building_id=annex.id, name="Ground"),
    ]
    session.add_all(floors)
    session.flush()

    seats = [
        Seat(floor_id=floors[0].id, label="1-A12"),
        Seat(floor_id=floors[0].id, label="1-A13"),
        Seat(floor_id=floors[1].id, label="2-B04"),
        Seat(floor_id=floors[2].id, label="G-C01"),
    ]
    session.add_all(seats)
    session.flush()

    # --- Incidents ----------------------------------------------------------
    # Spread across all five statuses, several categories and priorities, with
    # lifecycle timestamps set so Step 5's time-to-acknowledge and
    # time-to-resolve averages have something real to compute.
    incidents = [
        Incident(
            title="Meeting room AC blowing warm air",
            description="Level 2 south meeting room has been at 27C since Monday.",
            category="hvac",
            status=IncidentStatus.OPEN,
            priority=IncidentPriority.HIGH,
            building_id=hq.id,
            floor_id=floors[1].id,
            reporter_id=employee_one.id,
            created_at=ago(hours=6),
        ),
        Incident(
            title="Desk power socket dead",
            description="No power at seat 1-A12; laptop charger confirmed working elsewhere.",
            category="electrical",
            status=IncidentStatus.IN_PROGRESS,
            priority=IncidentPriority.MEDIUM,
            building_id=hq.id,
            floor_id=floors[0].id,
            seat_id=seats[0].id,
            reporter_id=employee_two.id,
            assignee_id=engineer_one.id,
            acknowledged_at=ago(days=1, hours=20),
            assigned_at=ago(days=1, hours=20),
            created_at=ago(days=2),
        ),
        Incident(
            title="Wi-Fi drops every few minutes near the annex kitchen",
            description="Affects the whole Ground floor east side.",
            category="network",
            status=IncidentStatus.BLOCKED,
            priority=IncidentPriority.URGENT,
            blocked_reason="Waiting on the replacement access point from the vendor.",
            escalation_requested=True,
            escalated=True,
            escalation_reason="Three days of repeated dropouts affecting the annex team.",
            building_id=annex.id,
            floor_id=floors[2].id,
            reporter_id=employee_one.id,
            assignee_id=engineer_two.id,
            acknowledged_at=ago(days=3, hours=1),
            assigned_at=ago(days=3, hours=1),
            created_at=ago(days=3, hours=4),
        ),
        Incident(
            title="Broken chair gas lift",
            description="Chair at 2-B04 sinks to the lowest position immediately.",
            category="furniture",
            status=IncidentStatus.RESOLVED,
            priority=IncidentPriority.LOW,
            building_id=hq.id,
            floor_id=floors[1].id,
            seat_id=seats[2].id,
            reporter_id=employee_two.id,
            assignee_id=engineer_one.id,
            acknowledged_at=ago(days=5, hours=22),
            assigned_at=ago(days=5, hours=22),
            resolved_at=ago(days=4),
            created_at=ago(days=6),
        ),
        Incident(
            title="Badge reader rejects valid badges at the annex door",
            description="Roughly one in three badge taps is refused.",
            category="access_security",
            status=IncidentStatus.CLOSED,
            priority=IncidentPriority.HIGH,
            building_id=annex.id,
            floor_id=floors[2].id,
            reporter_id=employee_one.id,
            assignee_id=engineer_two.id,
            acknowledged_at=ago(days=9, hours=23),
            assigned_at=ago(days=9, hours=23),
            resolved_at=ago(days=8),
            closed_at=ago(days=7),
            created_at=ago(days=10),
        ),
        Incident(
            title="Leaking tap in the Level 1 kitchen",
            description="Slow but constant drip; the cabinet underneath is damp.",
            category="plumbing",
            status=IncidentStatus.OPEN,
            priority=IncidentPriority.MEDIUM,
            building_id=hq.id,
            floor_id=floors[0].id,
            reporter_id=employee_two.id,
            created_at=ago(hours=2),
        ),
    ]
    session.add_all(incidents)
    backdate(incidents)
    session.flush()

    # --- Threads and history ------------------------------------------------
    session.add_all(
        [
            IncidentNote(
                incident_id=incidents[1].id,
                author_id=engineer_user_one.id,
                body="Confirmed the circuit is dead at the wall. Replacement socket ordered.",
            ),
            IncidentNote(
                incident_id=incidents[2].id,
                author_id=employee_one.id,
                body="Still dropping this morning — three calls cut off.",
            ),
            IncidentNote(
                incident_id=incidents[2].id,
                author_id=engineer_user_two.id,
                body="Vendor has shipped the access point, arriving Thursday.",
            ),
        ]
    )

    # One row per transition each incident has actually been through. Step 5
    # writes these automatically; here they are stated explicitly so the
    # dashboard has history to aggregate from the first run.
    history = []
    for incident in incidents:
        history.append(
            IncidentStatusHistory(
                incident_id=incident.id,
                from_status=None,
                to_status=IncidentStatus.OPEN,
                changed_by=incident.reporter_id,
                changed_at=incident.created_at,
            )
        )
        if incident.assigned_at:
            history.append(
                IncidentStatusHistory(
                    incident_id=incident.id,
                    from_status=IncidentStatus.OPEN,
                    to_status=IncidentStatus.IN_PROGRESS,
                    changed_by=admin.id,
                    changed_at=incident.assigned_at,
                )
            )
        if incident.status == IncidentStatus.BLOCKED:
            history.append(
                IncidentStatusHistory(
                    incident_id=incident.id,
                    from_status=IncidentStatus.IN_PROGRESS,
                    to_status=IncidentStatus.BLOCKED,
                    changed_by=engineer_user_two.id,
                    changed_at=ago(days=2),
                )
            )
        if incident.resolved_at:
            history.append(
                IncidentStatusHistory(
                    incident_id=incident.id,
                    from_status=IncidentStatus.IN_PROGRESS,
                    to_status=IncidentStatus.RESOLVED,
                    changed_by=incident.reporter_id,
                    changed_at=incident.resolved_at,
                )
            )
        if incident.closed_at:
            history.append(
                IncidentStatusHistory(
                    incident_id=incident.id,
                    from_status=IncidentStatus.RESOLVED,
                    to_status=IncidentStatus.CLOSED,
                    changed_by=admin.id,
                    changed_at=incident.closed_at,
                )
            )
    session.add_all(history)

    # A pending request on an unassigned incident, so the Step 5 admin queue and
    # the Step 6 approve/deny panel have something to show immediately.
    session.add(
        IncidentAssignmentRequest(incident_id=incidents[0].id, engineer_id=engineer_one.id)
    )

    return {
        "users": 5,
        "engineer_profiles": 2,
        "buildings": 2,
        "floors": len(floors),
        "seats": len(seats),
        "incidents": len(incidents),
        "notes": 3,
        "status_history": len(history),
        "assignment_requests": 1,
    }


def main() -> int:
    """Entry point. Returns a process exit code."""
    parser = argparse.ArgumentParser(description="Seed the local incident database.")
    parser.add_argument("--reset", action="store_true", help="delete existing rows first")
    args = parser.parse_args()

    # Hard stop outside local development. The seeded accounts share one known
    # password, so running this against Aurora would hand out five working
    # logins, one of them a Facility Admin.
    if not is_local():
        print("Refusing to seed: IS_LOCAL is not 'true'. This script is for local development only.")
        return 1

    with session_scope() as session:
        existing = session.scalar(select(User).limit(1))
        if existing and not args.reset:
            print("Database already contains users. Re-run with --reset to replace the data.")
            return 1
        if args.reset:
            clear_all(session)
        counts = seed(session)

    print("Seeded:")
    for entity, count in counts.items():
        print(f"  {count:>3}  {entity}")
    print(f"\nAll accounts use the password: {SEED_PASSWORD}")
    print("  dana.admin@acme.inc      facility_admin")
    print("  sam.employee@acme.inc    employee")
    print("  priya.employee@acme.inc  employee")
    print("  alex.engineer@acme.inc   engineer (available)")
    print("  jo.engineer@acme.inc     engineer (busy)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
