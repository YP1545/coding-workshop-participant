/**
 * Tests for the incident list.
 *
 * Part of: frontend / tests.
 *
 * Searching, filtering and paging are all done by the API, so what these tests
 * pin down is what the page asks for. The subtle rule is the page reset: a
 * filter changed while on page 4 must go back to page 1, or somebody narrows
 * their search and lands on an empty page wondering where everything went.
 */

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import IncidentsPage from './IncidentsPage'
import * as engineersApi from '../api/engineersApi'
import * as facilitiesApi from '../api/facilitiesApi'
import * as incidentsApi from '../api/incidentsApi'
import { renderWithProviders } from '../test/render'

vi.mock('../api/incidentsApi')
vi.mock('../api/facilitiesApi')
vi.mock('../api/engineersApi')

function incident(number) {
  return {
    id: `incident-${number}`, title: `Leaking tap ${number}`,
    description: 'Slow but constant drip.', category: 'plumbing',
    status: 'open', priority: 'medium', escalated: false,
    created_at: '2026-09-22T10:00:00+00:00',
  }
}

/** A page of results, as the API returns it. */
function pageOf(count, total) {
  return {
    items: Array.from({ length: count }, (unused, index) => incident(index)),
    total, limit: 10, offset: 0,
  }
}

describe('IncidentsPage', () => {
  beforeEach(() => {
    incidentsApi.listIncidents.mockResolvedValue(pageOf(10, 25))
    facilitiesApi.listBuildings.mockResolvedValue([{ id: 'building-1', name: 'HQ Tower' }])
    // The table turns an assignee id into a name, so the page loads the roster.
    engineersApi.listEngineers.mockResolvedValue([])
    // Categories come from the database now, so the filter dropdown fetches them.
    incidentsApi.listCategories.mockResolvedValue([
      { slug: 'plumbing', name: 'Plumbing', sort_order: 30 },
      { slug: 'other', name: 'Other', sort_order: 90 },
    ])
  })

  it('asks for the first ten', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')

    expect(incidentsApi.listIncidents).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 10, offset: 0 }))
  })

  it('says how many there are and which page this is', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })

    expect(await screen.findByText(/25 incidents found/)).toBeInTheDocument()
    expect(screen.getByText(/page 1 of 3/)).toBeInTheDocument()
  })

  it('asks for the next ten when the page changes', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')

    await userEvent.click(screen.getByRole('button', { name: /go to page 2/i }))

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 10, offset: 10 }))
    })
  })

  it('hides the page controls when everything fits on one page', async () => {
    incidentsApi.listIncidents.mockResolvedValue(pageOf(3, 3))

    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')

    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('searches for what was typed, once Enter is pressed', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')

    await userEvent.type(screen.getByLabelText(/search incidents/i), 'radiator{Enter}')

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'radiator' }))
    })
  })

  it('does not fire a request for every keystroke', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')
    const before = incidentsApi.listIncidents.mock.calls.length

    await userEvent.type(screen.getByLabelText(/search incidents/i), 'radiator')

    expect(incidentsApi.listIncidents.mock.calls.length).toBe(before)
  })

  it('goes back to the first page when a filter changes', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')

    await userEvent.click(screen.getByRole('button', { name: /go to page 3/i }))
    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 20 }))
    })

    await userEvent.click(screen.getByLabelText('Status'))
    await userEvent.click(await screen.findByRole('option', { name: 'Blocked' }))

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'blocked', offset: 0 }))
    })
  })

  it('offers a way out of a search that found nothing', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'employee' })
    await screen.findByText('Leaking tap 0')
    incidentsApi.listIncidents.mockResolvedValue(pageOf(0, 0))

    await userEvent.type(screen.getByLabelText(/search incidents/i), 'nothing{Enter}')

    expect(await screen.findByText(/Nothing matches "nothing"/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument()
  })

  it('shows the API error rather than an empty list', async () => {
    incidentsApi.listIncidents.mockRejectedValue({ status: 401, detail: 'Authentication required' })

    renderWithProviders(<IncidentsPage />, { as: 'employee' })

    expect(await screen.findByText('Authentication required')).toBeInTheDocument()
  })

  it('tells an engineer what they are looking at', async () => {
    renderWithProviders(<IncidentsPage />, { as: 'engineer' })

    expect(await screen.findByText(/Assigned to you, plus open work/)).toBeInTheDocument()
  })

  it('runs a search that arrived in the URL from the bar in the app frame', async () => {
    renderWithProviders(<IncidentsPage />, { route: '/incidents?search=radiator' })

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'radiator', offset: 0 }),
      )
    })

    // The box shows the term too, so it can be edited rather than retyped.
    expect(screen.getByLabelText(/search incidents/i)).toHaveValue('radiator')
  })
})
