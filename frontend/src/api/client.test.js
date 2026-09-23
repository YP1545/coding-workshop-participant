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

function respondWith(status, payload) {
  return vi.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
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
      status: 500, ok: false, json: () => Promise.reject(new Error('not json')),
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
