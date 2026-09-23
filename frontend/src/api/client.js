/**
 * HTTP client shared by every API module.
 *
 * Requests go to `${API_URL}/api/${service}${path}`. Locally, API_URL points at
 * the CORS proxy on :3001 (bin/proxy-server.js), which maps /api/{service} onto
 * that service's Lambda Function URL. On AWS, API_URL is the CloudFront domain
 * and the same path is routed to the same Lambda, so callers never change.
 */

// In development, requests go to the Vite dev server's own origin and its proxy
// forwards them (see vite.config.js) — that path preserves the Authorization
// header, which the scaffold's :3001 CORS proxy strips. In a build, VITE_API_URL
// is the CloudFront domain, which forwards all viewer headers except Host.
const API_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL || '')

// Bearer token for the current session. Held in a module variable rather than
// read from storage on every call, and kept in sync by setAuthToken so there is
// one place that decides what "signed in" means.
let authToken = null

/**
 * Set or clear the bearer token used for subsequent requests.
 *
 * @param {string|null} token The JWT from POST /auth/login, or null to sign out.
 */
export function setAuthToken(token) {
  authToken = token || null
}

/** Return the token currently in use, if any. */
export function getAuthToken() {
  return authToken
}

export const SERVICES = {
  users: 'users-service',
  facilities: 'facilities-service',
  engineers: 'engineers-service',
  incidents: 'incidents-service',
}

/**
 * An HTTP error carrying the API's `detail` message and the status code.
 */
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

/**
 * Perform a request against one service.
 *
 * @param {string} service One of the SERVICES values.
 * @param {string} path Path within the service, e.g. '/incidents'.
 * @param {object} [options] method, body (auto-serialized), and query params.
 * @returns {Promise<any>} Parsed JSON, or null for a 204.
 */
export async function request(service, path, { method = 'GET', body, query } = {}) {
  // Drop empty filters before building the query string. URLSearchParams
  // stringifies undefined and null into the literal text "undefined"/"null",
  // so `{ status: undefined }` would otherwise filter for a status named
  // "undefined" and return nothing.
  const entries = Object.entries(query || {}).filter(
    ([, value]) => value !== undefined && value !== null && value !== '',
  )
  const search = entries.length ? `?${new URLSearchParams(entries)}` : ''
  const headers = { 'Content-Type': 'application/json' }
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  const response = await fetch(`${API_URL}/api/${service}${path}${search}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 204) return null

  // CloudFront rewrites every 404 in the distribution to /index.html with a
  // 200, so that a deep link into the single-page app loads the app instead of
  // an error (infra/cloudfront.tf custom_error_response). That rule is not
  // scoped to the site's own paths, so an API 404 arrives here as 200 with an
  // HTML body — losing its status on the way through.
  //
  // Without this check `response.ok` is true, parsing HTML as JSON fails, and
  // the caller gets an empty object rather than an error: opening a deleted
  // incident would render a blank page instead of saying it is gone. There is
  // no way to fix it at the edge without changing infra/, which this project
  // treats as fixed, so it is recognised here instead.
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('json')) {
    throw new ApiError(404, 'Not found')
  }

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(response.status, payload.detail || `Request failed (${response.status})`)
  }
  return payload
}

/** Check one service's /health endpoint. */
export function checkHealth(service) {
  return request(service, '/health')
}
