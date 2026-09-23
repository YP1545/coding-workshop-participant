/**
 * Calls to the users service: registering, signing in, and "who am I".
 *
 * Part of: frontend / api layer.
 *
 * Why its own file: every page that talks to the backend goes through one of
 * these api modules instead of calling fetch itself. That way the URLs live in
 * one place, and a component never has to know how the API is shaped.
 */

import { SERVICES, request } from './client'

/** Create a new employee account. */
export function register(email, password, fullName) {
  return request(SERVICES.users, '/auth/register', {
    method: 'POST',
    body: { email, password, full_name: fullName },
  })
}

/** Sign in. Returns { access_token, token_type, user }. */
export function login(email, password) {
  return request(SERVICES.users, '/auth/login', {
    method: 'POST',
    body: { email, password },
  })
}

/** Fetch the signed-in user, using the token the client is holding. */
export function getCurrentUser() {
  return request(SERVICES.users, '/auth/me')
}

/** List all accounts. Facility admins only. */
export function listUsers(role) {
  return request(SERVICES.users, '/users', { query: { role } })
}

/** Change someone's role. Facility admins only. */
export function updateUserRole(userId, role) {
  return request(SERVICES.users, `/users/${userId}/role`, {
    method: 'PATCH',
    body: { role },
  })
}
