"""
Facilities service: the building > floor > seat hierarchy.

Part of: backend / facilities service (one Lambda).

Why its own service: facility structure changes rarely and is read by every
other part of the product, so it is isolated from the incident write path.

Access rule: any signed-in person may read the tree — an employee reporting a
fault has to pick their building — while every write is facility_admin only.
Each route says which in its own signature.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import create_app, lambda_handler
from crud import delete, ensure_exists, get_or_404, save
from deps import ADMIN_ONLY, get_current_user, get_session, require_roles
from models import Building, Floor, Seat, User
from schemas import BuildingIn, BuildingOut, FloorIn, FloorOut, SeatIn, SeatOut

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_NAME = "facilities-service"

app = create_app(SERVICE_NAME, "ACME Facility Incidents — buildings, floors and seats")
router = APIRouter()


# --- Buildings --------------------------------------------------------------


@router.post("/buildings", response_model=BuildingOut, status_code=201, tags=["buildings"])
def create_building(
    payload: BuildingIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Create a building."""
    building = Building(name=payload.name, address=payload.address)
    session.add(building)
    save(session, building, conflict="A building with that name already exists")
    return building


@router.get("/buildings", response_model=list[BuildingOut], tags=["buildings"])
def list_buildings(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List buildings, newest first."""
    return session.scalars(
        select(Building).order_by(Building.created_at.desc()).limit(limit).offset(offset)
    ).all()


@router.get("/buildings/{building_id}", response_model=BuildingOut, tags=["buildings"])
def get_building(
    building_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Fetch one building."""
    return get_or_404(session, Building, building_id, "Building")


@router.put("/buildings/{building_id}", response_model=BuildingOut, tags=["buildings"])
def update_building(
    building_id: uuid.UUID,
    payload: BuildingIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Update a building.

    Name is required. Address is left unchanged when omitted and cleared by
    sending an explicit null — model_fields_set is what tells those two apart.
    Treating "absent" as "clear it" silently destroys data when a form sends
    only the fields somebody edited.
    """
    building = get_or_404(session, Building, building_id, "Building")
    building.name = payload.name
    if "address" in payload.model_fields_set:
        building.address = payload.address
    save(session, building, conflict="A building with that name already exists")
    return building


@router.delete("/buildings/{building_id}", status_code=204, tags=["buildings"])
def delete_building(
    building_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Delete a building. 409 while floors still reference it."""
    delete(session, get_or_404(session, Building, building_id, "Building"), "Building")


# --- Floors -----------------------------------------------------------------


@router.post("/buildings/{building_id}/floors", response_model=FloorOut, status_code=201,
             tags=["floors"])
def create_floor(
    building_id: uuid.UUID,
    payload: FloorIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Create a floor inside a building."""
    ensure_exists(session, Building, building_id, "Building")
    floor = Floor(building_id=building_id, name=payload.name)
    session.add(floor)
    save(session, floor, conflict="A floor with that name already exists in this building")
    return floor


@router.get("/buildings/{building_id}/floors", response_model=list[FloorOut], tags=["floors"])
def list_floors(
    building_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List the floors of one building, ordered by name for a stable tree."""
    ensure_exists(session, Building, building_id, "Building")
    return session.scalars(
        select(Floor).where(Floor.building_id == building_id).order_by(Floor.name)
    ).all()


@router.put("/floors/{floor_id}", response_model=FloorOut, tags=["floors"])
def update_floor(
    floor_id: uuid.UUID,
    payload: FloorIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Rename a floor."""
    floor = get_or_404(session, Floor, floor_id, "Floor")
    floor.name = payload.name
    save(session, floor, conflict="A floor with that name already exists in this building")
    return floor


@router.delete("/floors/{floor_id}", status_code=204, tags=["floors"])
def delete_floor(
    floor_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Delete a floor. 409 while seats still reference it."""
    delete(session, get_or_404(session, Floor, floor_id, "Floor"), "Floor")


# --- Seats ------------------------------------------------------------------


@router.post("/floors/{floor_id}/seats", response_model=SeatOut, status_code=201, tags=["seats"])
def create_seat(
    floor_id: uuid.UUID,
    payload: SeatIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Create a seat on a floor."""
    ensure_exists(session, Floor, floor_id, "Floor")
    seat = Seat(floor_id=floor_id, label=payload.label)
    session.add(seat)
    save(session, seat, conflict="A seat with that label already exists on this floor")
    return seat


@router.get("/floors/{floor_id}/seats", response_model=list[SeatOut], tags=["seats"])
def list_seats(
    floor_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List the seats on one floor, ordered by label."""
    ensure_exists(session, Floor, floor_id, "Floor")
    return session.scalars(
        select(Seat).where(Seat.floor_id == floor_id).order_by(Seat.label)
    ).all()


@router.put("/seats/{seat_id}", response_model=SeatOut, tags=["seats"])
def update_seat(
    seat_id: uuid.UUID,
    payload: SeatIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """Relabel a seat."""
    seat = get_or_404(session, Seat, seat_id, "Seat")
    seat.label = payload.label
    save(session, seat, conflict="A seat with that label already exists on this floor")
    return seat


@router.delete("/seats/{seat_id}", status_code=204, tags=["seats"])
def delete_seat(
    seat_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(ADMIN_ONLY)),
):
    """
    Delete a seat.

    Incidents referencing it are not blocked: incidents.seat_id is ON DELETE
    SET NULL, so the history of what went wrong there survives the seat.
    """
    delete(session, get_or_404(session, Seat, seat_id, "Seat"), "Seat")


app.include_router(router)

handler = lambda_handler(app, SERVICE_NAME)
