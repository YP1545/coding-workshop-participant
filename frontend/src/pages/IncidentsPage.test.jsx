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
    facilitiesApi.listBuildings.mockResolvedValue([
      { id: 'building-1', name: 'HQ Tower' },
      { id: 'building-2', name: 'Riverside Annex' },
    ])
    facilitiesApi.listFloors.mockResolvedValue([{ id: 'floor-1', name: 'Level 1' }])
    facilitiesApi.listSeats.mockResolvedValue([{ id: 'seat-1', label: '1-A12' }])
    // The table turns an assignee id into a name, so the page loads the roster.
    engineersApi.listEngineers.mockResolvedValue([
      { id: 'engineer-1', full_name: 'Alex Chen', availability: 'available' },
    ])
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

describe('IncidentsPage location filters', () => {
  beforeEach(() => {
    incidentsApi.listIncidents.mockResolvedValue(pageOf(10, 25))
    incidentsApi.listCategories.mockResolvedValue([])
    facilitiesApi.listBuildings.mockResolvedValue([
      { id: 'building-1', name: 'HQ Tower' },
      { id: 'building-2', name: 'Riverside Annex' },
    ])
    facilitiesApi.listFloors.mockResolvedValue([{ id: 'floor-1', name: 'Level 1' }])
    facilitiesApi.listSeats.mockResolvedValue([{ id: 'seat-1', label: '1-A12' }])
    engineersApi.listEngineers.mockResolvedValue([
      { id: 'engineer-1', full_name: 'Alex Chen', availability: 'available' },
    ])
  })

  it('will not let you pick a floor before a building', async () => {
    renderWithProviders(<IncidentsPage />)

    // A floor means nothing without its building, and an enabled dropdown with
    // nothing in it looks broken rather than unavailable.
    const floor = await screen.findByLabelText(/floor/i)
    expect(floor).toHaveAttribute('aria-disabled', 'true')
  })

  it('loads a building\'s floors once one is chosen', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IncidentsPage />)

    await user.click(await screen.findByLabelText(/building/i))
    await user.click(await screen.findByRole('option', { name: 'HQ Tower' }))

    await waitFor(() => {
      expect(facilitiesApi.listFloors).toHaveBeenCalledWith('building-1')
    })
  })

  it('clears the floor when the building changes', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IncidentsPage />)

    await user.click(await screen.findByLabelText(/building/i))
    await user.click(await screen.findByRole('option', { name: 'HQ Tower' }))
    await user.click(await screen.findByLabelText(/floor/i))
    await user.click(await screen.findByRole('option', { name: 'Level 1' }))

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenCalledWith(
        expect.objectContaining({ building_id: 'building-1', floor_id: 'floor-1' }),
      )
    })

    // Switching building must drop the floor with it: asking for a floor that
    // is not in the selected building returns nothing, which reads as "no
    // incidents" rather than "those two filters contradict each other".
    await user.click(screen.getByLabelText(/building/i))
    await user.click(await screen.findByRole('option', { name: 'Riverside Annex' }))

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenLastCalledWith(
        expect.objectContaining({ building_id: 'building-2', floor_id: '' }),
      )
    })
  })

  it('filters by assignee, which is how an admin sees one engineer\'s plate', async () => {
    const user = userEvent.setup()
    renderWithProviders(<IncidentsPage />)

    await user.click(await screen.findByLabelText(/assignee/i))
    await user.click(await screen.findByRole('option', { name: 'Alex Chen' }))

    await waitFor(() => {
      expect(incidentsApi.listIncidents).toHaveBeenCalledWith(
        expect.objectContaining({ assignee_id: 'engineer-1', offset: 0 }),
      )
    })
  })
})
