/**
 * Tests for the incident detail page.
 *
 * Part of: frontend / tests.
 *
 * Every action panel here is shown to one role and hidden from the others, and
 * that gating is where this page went wrong in a way the backend tests could
 * not see: an engineer could not act on their own assigned incident, because
 * the page never learned their engineer profile id. The API was correct
 * throughout — only the browser was wrong. These tests cover that gap.
 */

import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import IncidentDetailPage from './IncidentDetailPage'
import * as engineersApi from '../api/engineersApi'
import * as incidentsApi from '../api/incidentsApi'
import { PEOPLE, renderWithProviders } from '../test/render'

vi.mock('../api/incidentsApi')
vi.mock('../api/engineersApi')

// react-router's useParams needs a value; the route is not what is under test.
vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual('react-router-dom')),
  useParams: () => ({ incidentId: 'incident-1' }),
}))

const ENGINEER_PROFILE = {
  id: 'profile-engineer', user_id: PEOPLE.engineer.id,
  full_name: 'Alex Chen', email: 'alex.engineer@acme.inc',
  availability: 'available', specialty: 'HVAC',
}

function incident(overrides) {
  return {
    id: 'incident-1', title: 'Desk power socket dead', description: 'No power at 1-A12.',
    category: 'electrical', status: 'open', priority: 'medium',
    building_id: null, floor_id: null, seat_id: null,
    reporter_id: PEOPLE.employee.id, assignee_id: null,
    escalation_requested: false, escalated: false,
    escalation_reason: null, blocked_reason: null,
    acknowledged_at: null, assigned_at: null, resolved_at: null, closed_at: null,
    created_at: '2026-09-20T10:00:00+00:00', updated_at: '2026-09-20T10:00:00+00:00',
    ...overrides,
  }
}

function setup(overrides = {}) {
  incidentsApi.getIncident.mockResolvedValue(incident(overrides))
  incidentsApi.listNotes.mockResolvedValue([])
  incidentsApi.listRequestsForIncident.mockResolvedValue([])
  engineersApi.listEngineers.mockResolvedValue([ENGINEER_PROFILE])
}

describe('IncidentDetailPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows an assigned engineer the status panel and the note box', async () => {
    setup({ assignee_id: ENGINEER_PROFILE.id, status: 'in_progress' })

    renderWithProviders(<IncidentDetailPage />, { as: 'engineer' })
    await screen.findByText('Desk power socket dead')

    expect(screen.getByRole('heading', { name: 'Update status' })).toBeInTheDocument()
    expect(screen.getByLabelText('Add a note')).toBeInTheDocument()
  })

  it('offers an unassigned engineer the job rather than the controls', async () => {
    setup({ assignee_id: null, status: 'open' })

    renderWithProviders(<IncidentDetailPage />, { as: 'engineer' })
    await screen.findByText('Desk power socket dead')

    expect(screen.getByRole('button', { name: /request assignment/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Update status' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Add a note')).not.toBeInTheDocument()
  })

  it('lets the reporter comment and ask for escalation, but not change status', async () => {
    setup({})

    renderWithProviders(<IncidentDetailPage />, { as: 'employee' })
    await screen.findByText('Desk power socket dead')

    expect(screen.getByLabelText('Add a note')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ask for escalation' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Update status' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Assign' })).not.toBeInTheDocument()
  })

  it('gives an admin every control', async () => {
    setup({})

    renderWithProviders(<IncidentDetailPage />, { as: 'admin' })
    await screen.findByText('Desk power socket dead')

    expect(screen.getByRole('heading', { name: 'Update status' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Assign' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete incident/i })).toBeInTheDocument()
  })

  it('names the engineer on a pending request, rather than showing an id', async () => {
    setup({})
    incidentsApi.listRequestsForIncident.mockResolvedValue([{
      id: 'request-1', incident_id: 'incident-1', engineer_id: ENGINEER_PROFILE.id,
      status: 'pending', requested_at: '2026-09-22T10:00:00+00:00',
      decided_at: null, decided_by: null,
      engineer_name: 'Alex Chen', engineer_email: 'alex.engineer@acme.inc',
    }])

    renderWithProviders(<IncidentDetailPage />, { as: 'admin' })
    await screen.findByText('Desk power socket dead')

    expect(await screen.findByText('Alex Chen')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
  })

  it('shows the blocked reason on the stepper', async () => {
    setup({ status: 'blocked', blocked_reason: 'Waiting on a part from the supplier' })

    renderWithProviders(<IncidentDetailPage />, { as: 'employee' })
    await screen.findByText('Desk power socket dead')

    expect(screen.getByText(/Waiting on a part from the supplier/)).toBeInTheDocument()
  })
})
