/**
 * Calls to the engineers service: profiles and availability.
 *
 * Part of: frontend / api layer.
 */

import { SERVICES, request } from './client'

/** List engineer profiles, optionally filtered by availability. */
export function listEngineers(availability) {
  return request(SERVICES.engineers, '/engineers', { query: { availability } })
}

/** Fetch one engineer profile. */
export function getEngineer(engineerId) {
  return request(SERVICES.engineers, `/engineers/${engineerId}`)
}

/** Promote an existing account to engineer. Facility admins only. */
export function createEngineerFromUser(userId, specialty) {
  return request(SERVICES.engineers, '/engineers', {
    method: 'POST',
    body: { user_id: userId, specialty },
  })
}

/** Create a brand new engineer account. Facility admins only. */
export function createEngineerAccount(email, fullName, specialty) {
  return request(SERVICES.engineers, '/engineers', {
    method: 'POST',
    body: { email, full_name: fullName, specialty },
  })
}

/**
 * Update an engineer profile.
 *
 * An admin may change both fields. An engineer may change only their own
 * availability — the backend enforces that, this just sends what was asked.
 */
export function updateEngineer(engineerId, changes) {
  return request(SERVICES.engineers, `/engineers/${engineerId}`, {
    method: 'PUT',
    body: changes,
  })
}

/** Remove someone from the engineer roster. Their account stays. */
export function deleteEngineer(engineerId) {
  return request(SERVICES.engineers, `/engineers/${engineerId}`, { method: 'DELETE' })
}
