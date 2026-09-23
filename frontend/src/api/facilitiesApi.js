/**
 * Calls to the facilities service: buildings, floors and seats.
 *
 * Part of: frontend / api layer.
 */

import { SERVICES, request } from './client'

/** List all buildings. */
export function listBuildings() {
  return request(SERVICES.facilities, '/buildings')
}

/** Create a building. Facility admins only. */
export function createBuilding(name, address) {
  return request(SERVICES.facilities, '/buildings', {
    method: 'POST',
    body: { name, address },
  })
}

/** Rename or re-address a building. */
export function updateBuilding(buildingId, name, address) {
  return request(SERVICES.facilities, `/buildings/${buildingId}`, {
    method: 'PUT',
    body: { name, address },
  })
}

/** Delete a building. Fails with 409 if it still has floors. */
export function deleteBuilding(buildingId) {
  return request(SERVICES.facilities, `/buildings/${buildingId}`, { method: 'DELETE' })
}

/** List the floors in one building. */
export function listFloors(buildingId) {
  return request(SERVICES.facilities, `/buildings/${buildingId}/floors`)
}

/** Add a floor to a building. */
export function createFloor(buildingId, name) {
  return request(SERVICES.facilities, `/buildings/${buildingId}/floors`, {
    method: 'POST',
    body: { name },
  })
}

/** Rename a floor. */
export function updateFloor(floorId, name) {
  return request(SERVICES.facilities, `/floors/${floorId}`, { method: 'PUT', body: { name } })
}

/** Delete a floor. Fails with 409 if it still has seats. */
export function deleteFloor(floorId) {
  return request(SERVICES.facilities, `/floors/${floorId}`, { method: 'DELETE' })
}

/** List the seats on one floor. */
export function listSeats(floorId) {
  return request(SERVICES.facilities, `/floors/${floorId}/seats`)
}

/** Add a seat to a floor. */
export function createSeat(floorId, label) {
  return request(SERVICES.facilities, `/floors/${floorId}/seats`, {
    method: 'POST',
    body: { label },
  })
}

/** Relabel a seat. */
export function updateSeat(seatId, label) {
  return request(SERVICES.facilities, `/seats/${seatId}`, { method: 'PUT', body: { label } })
}

/** Delete a seat. */
export function deleteSeat(seatId) {
  return request(SERVICES.facilities, `/seats/${seatId}`, { method: 'DELETE' })
}
