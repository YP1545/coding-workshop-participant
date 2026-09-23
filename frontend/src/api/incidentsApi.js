/**
 * Calls to the incidents service: incidents, notes, the workflow, and the
 * dashboard numbers.
 *
 * Part of: frontend / api layer.
 *
 * Why its own file: this is the biggest part of the API, and keeping it apart
 * from facilities and engineers means a page imports only what it actually
 * uses.
 */

import { SERVICES, request } from './client'

/**
 * List incidents the signed-in user is allowed to see, one page at a time.
 *
 * @param {object} [filters] status, priority, category, building_id, search,
 *   limit and offset. Empty values are dropped by the client.
 * @returns {Promise<{items: object[], total: number, limit: number, offset: number}>}
 *   total is how many match the filters, not how many are on this page — it is
 *   what lets the page controls say "of 5".
 */
export function listIncidents(filters) {
  return request(SERVICES.incidents, '/incidents', { query: filters })
}

/** Fetch one incident. */
export function getIncident(incidentId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}`)
}

/** Report a new incident. The backend records the reporter from the token. */
export function createIncident(incident) {
  return request(SERVICES.incidents, '/incidents', { method: 'POST', body: incident })
}

/** Edit an incident's description fields. */
export function updateIncident(incidentId, changes) {
  return request(SERVICES.incidents, `/incidents/${incidentId}`, {
    method: 'PUT',
    body: changes,
  })
}

/** Delete an incident. Facility admins only. */
export function deleteIncident(incidentId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}`, { method: 'DELETE' })
}

/**
 * Move an incident to a new status.
 *
 * @param {string} blockedReason Required by the backend when status is 'blocked'.
 */
export function changeStatus(incidentId, status, blockedReason) {
  const body = { status }
  if (blockedReason) body.blocked_reason = blockedReason
  return request(SERVICES.incidents, `/incidents/${incidentId}/status`, {
    method: 'PATCH',
    body,
  })
}

/** Assign an incident to an engineer, or pass null to unassign it. */
export function assignIncident(incidentId, engineerId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/assign`, {
    method: 'PATCH',
    body: { assignee_id: engineerId },
  })
}

/** Ask for an incident to be escalated (reporter), with the reason why. */
export function requestEscalation(incidentId, reason) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/escalate`, {
    method: 'PATCH',
    body: { escalation_requested: true, escalation_reason: reason },
  })
}

/** Confirm or withdraw an escalation. Facility admins only. */
export function setEscalated(incidentId, escalated) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/escalate`, {
    method: 'PATCH',
    body: { escalated },
  })
}

/** List the notes on an incident, oldest first. */
export function listNotes(incidentId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/notes`)
}

/** Add a note. The backend records the author from the token. */
export function addNote(incidentId, body) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/notes`, {
    method: 'POST',
    body: { body },
  })
}

/** Ask to be assigned an incident. Engineers only. */
export function requestAssignment(incidentId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/assignment-requests`, {
    method: 'POST',
  })
}

/** The requests made for one incident. */
export function listRequestsForIncident(incidentId) {
  return request(SERVICES.incidents, `/incidents/${incidentId}/assignment-requests`)
}

/** The admin's queue of assignment requests. */
export function listAllRequests(status) {
  return request(SERVICES.incidents, '/assignment-requests', { query: { status } })
}

/** The signed-in engineer's own requests. */
export function listMyRequests() {
  return request(SERVICES.incidents, '/engineers/me/assignment-requests')
}

/** Approve or deny a request. Facility admins only. */
export function decideRequest(requestId, status) {
  return request(SERVICES.incidents, `/assignment-requests/${requestId}`, {
    method: 'PATCH',
    body: { status },
  })
}

/** The dashboard numbers, already scoped to the signed-in user by the backend. */
export function getDashboardSummary() {
  return request(SERVICES.incidents, '/dashboard/summary')
}

/**
 * The categories an incident can be filed under, in dropdown order.
 *
 * Fetched rather than hardcoded: the list lives in the incident_categories
 * table, so adding a row there makes the category selectable without a
 * frontend change.
 */
export function listCategories() {
  return request(SERVICES.incidents, '/categories')
}
