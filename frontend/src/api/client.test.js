/**
 * Tests for the HTTP client every API call goes through.
 *
 * Part of: frontend / tests.
 *
 * This is small but load-bearing: it attaches the bearer token, turns the
 * server's {"detail": ...} into an error the pages can show, and builds the
 * query string. A mistake here is invisible until it is a blank page or a
 * request that silently arrives anonymous.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request, setAuthToken, SERVICES } from './client'

/**
 * A stand-in for fetch's Response.
 *
 * headers is included because the client reads content-type to recognise
 * CloudFront's rewritten 404s — a mock without it does not behave like the
 * thing being stood in for, and the difference only shows up once deployed.
 *
 * @param {number} status the HTTP status to return.
 * @param {*} payload the parsed JSON body.
 * @param {string} [contentType] override, for the not-JSON cases.
 */
function respondWith(status, payload, contentType = 'application/json') {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name) => (name === 'content-type' ? contentType : null) },
    json: () => Promise.resolve(payload),
  })
}

describe('the API client', () => {
  beforeEach(() => {
    setAuthToken(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends no Authorization header when signed out', async () => {
    const fetchMock = respondWith(200, [])
    vi.stubGlobal('fetch', fetchMock)

    await request(SERVICES.incidents, '/incidents')

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('attaches the bearer token once signed in', async () => {
    const fetchMock = respondWith(200, [])
    vi.stubGlobal('fetch', fetchMock)
    setAuthToken('a-token')

    await request(SERVICES.incidents, '/incidents')

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer a-token')
  })

  it('stops sending the token after signing out', async () => {
    const fetchMock = respondWith(200, [])
    vi.stubGlobal('fetch', fetchMock)
    setAuthToken('a-token')
    setAuthToken(null)

    await request(SERVICES.incidents, '/incidents')

    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })

  it('raises the server\'s own message so a page can show it', async () => {
    vi.stubGlobal('fetch', respondWith(409, { detail: 'A building with that name already exists' }))

    await expect(request(SERVICES.facilities, '/buildings', { method: 'POST' }))
      .rejects.toMatchObject({
        status: 409,
        detail: 'A building with that name already exists',
      })
  })

  it('still raises something useful when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      status: 500, ok: false,
      // Claims JSON but is not, which is what a crashed server actually sends.
      headers: { get: () => 'application/json' },
      json: () => Promise.reject(new Error('not json')),
    }))

    await expect(request(SERVICES.incidents, '/incidents')).rejects.toBeInstanceOf(ApiError)
  })

  it('returns null for a 204 rather than trying to parse it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 204, ok: true }))

    await expect(request(SERVICES.incidents, '/incidents/x', { method: 'DELETE' }))
      .resolves.toBeNull()
  })

  it('drops empty filters instead of sending them as text', async () => {
    const fetchMock = respondWith(200, [])
    vi.stubGlobal('fetch', fetchMock)

    await request(SERVICES.incidents, '/incidents', {
      query: { status: 'open', priority: undefined, category: '', building_id: null },
    })

    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('status=open')
    expect(url).not.toContain('undefined')
    expect(url).not.toContain('priority')
    expect(url).not.toContain('category')
  })

  it('sends no query string at all when every filter is empty', async () => {
    const fetchMock = respondWith(200, [])
    vi.stubGlobal('fetch', fetchMock)

    await request(SERVICES.incidents, '/incidents', { query: { status: '' } })

    expect(fetchMock.mock.calls[0][0]).not.toContain('?')
  })
})

describe('CloudFront rewriting 404s', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('treats an HTML body as not found, whatever status it arrived with', async () => {
    // What the deployed stack actually returns for a missing resource: the
    // distribution's custom_error_response turns the Lambda's 404 into a 200
    // serving /index.html. Without recognising it, response.ok is true and the
    // caller receives an empty object instead of an error.
    vi.stubGlobal('fetch', respondWith(200, null, 'text/html; charset=utf-8'))

    await expect(request(SERVICES.incidents, '/incidents/missing')).rejects.toMatchObject({
      status: 404,
      detail: 'Not found',
    })
  })

  it('still returns a normal JSON response', async () => {
    vi.stubGlobal('fetch', respondWith(200, { id: 'incident-1' }))

    await expect(request(SERVICES.incidents, '/incidents/incident-1'))
      .resolves.toEqual({ id: 'incident-1' })
  })

  it('leaves a 204 alone, which carries no content-type at all', async () => {
    vi.stubGlobal('fetch', respondWith(204, null, null))

    await expect(request(SERVICES.incidents, '/incidents/x', { method: 'DELETE' }))
      .resolves.toBeNull()
  })
})
