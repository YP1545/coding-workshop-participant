/**
 * Tests for the dashboard.
 *
 * Part of: frontend / tests.
 *
 * Three personas get three different dashboards, and the page picks from the
 * `role` in the response rather than from the signed-in user. These tests pin
 * that down in both directions: the right sections appear, and the ones that
 * belong to somebody else do not.
 */

import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from './DashboardPage'
import * as incidentsApi from '../api/incidentsApi'
import { renderWithProviders } from '../test/render'

vi.mock('../api/incidentsApi')

const EMPLOYEE_SUMMARY = {
  role: 'employee',
  counts_by_status: { open: 2, closed: 1 },
  counts_by_priority: { high: 1, medium: 2 },
  awaiting_count: 1,
  awaiting_your_attention: [{
    id: 'incident-1', title: 'Leaking tap', status: 'open',
    priority: 'medium', category: 'plumbing', created_at: '2026-09-22T10:00:00+00:00',
  }],
}

const ENGINEER_SUMMARY = {
  role: 'engineer',
  counts_by_status: { in_progress: 2 },
  counts_by_priority: { high: 2 },
  active_count: 2,
  assigned_incidents: [{
    id: 'incident-2', title: 'Desk power socket dead', status: 'in_progress',
    priority: 'medium', category: 'electrical', created_at: '2026-09-20T10:00:00+00:00',
  }],
  my_pending_requests: 1,
  open_to_request: 3,
  avg_hours_to_resolve: 12.5,
  needs_profile: false,
}

const ADMIN_SUMMARY = {
  role: 'facility_admin',
  counts_by_status: { open: 4, closed: 2 },
  counts_by_priority: { urgent: 1 },
  category_breakdown: { hvac: 3 },
  workload: [{ engineer_id: 'profile-1', name: 'Alex Chen', count: 3 }],
  unassigned_count: 1,
  avg_hours_to_acknowledge: 2.5,
  avg_hours_to_assign: 3.5,
  avg_hours_to_resolve: 48,
  top_locations: [{ building_id: 'building-1', name: 'HQ Tower', count: 4 }],
  escalated_blocked: [{
    id: 'incident-3', title: 'Wi-Fi drops', status: 'blocked', priority: 'urgent',
    escalated: true, escalation_reason: null, blocked_reason: 'Waiting on the vendor',
  }],
  engineer_availability: { available: 2, busy: 1, off: 0 },
  pending_assignment_requests: 1,
}

describe('DashboardPage', () => {
  beforeEach(() => {
    incidentsApi.getDashboardSummary.mockReset()
  })

  it('shows an employee their own tickets and what has news', async () => {
    incidentsApi.getDashboardSummary.mockResolvedValue(EMPLOYEE_SUMMARY)
    renderWithProviders(<DashboardPage />, { as: 'employee' })

    expect(await screen.findByText('Your incidents')).toBeInTheDocument()
    // "Waiting on you" is both a stat card and a section, so ask for the
    // heading specifically rather than any element with that text.
    expect(screen.getByRole('heading', { name: 'Waiting on you' })).toBeInTheDocument()
    expect(screen.getByText('Leaking tap')).toBeInTheDocument()
  })

  it('does not show an employee the site-wide sections', async () => {
    incidentsApi.getDashboardSummary.mockResolvedValue(EMPLOYEE_SUMMARY)
    renderWithProviders(<DashboardPage />, { as: 'employee' })
    await screen.findByText('Your incidents')

    expect(screen.queryByText(/Where problems keep happening/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Who is carrying the work/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Who is free/)).not.toBeInTheDocument()
  })

  it('shows an engineer their assigned work and what they could take', async () => {
    incidentsApi.getDashboardSummary.mockResolvedValue(ENGINEER_SUMMARY)
    renderWithProviders(<DashboardPage />, { as: 'engineer' })

    expect(await screen.findByText('Your work')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Assigned to you' })).toBeInTheDocument()
    expect(screen.getByText('Desk power socket dead')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Work you could take' })).toBeInTheDocument()
  })

  it('warns an engineer who has no profile that nothing can reach them', async () => {
    incidentsApi.getDashboardSummary.mockResolvedValue({
      ...ENGINEER_SUMMARY, needs_profile: true, assigned_incidents: [], active_count: 0,
    })
    renderWithProviders(<DashboardPage />, { as: 'engineer' })

    expect(await screen.findByText(/no engineer profile yet/)).toBeInTheDocument()
  })

  it('shows an admin the whole site, with engineers named', async () => {
    incidentsApi.getDashboardSummary.mockResolvedValue(ADMIN_SUMMARY)
    renderWithProviders(<DashboardPage />, { as: 'admin' })

    expect(await screen.findByText('Where problems keep happening')).toBeInTheDocument()
    expect(screen.getByText('HQ Tower')).toBeInTheDocument()
    expect(screen.getByText('Alex Chen: 3')).toBeInTheDocument()
    expect(screen.getByText(/Waiting on the vendor/)).toBeInTheDocument()
  })

  it('reports a failure instead of showing an empty page', async () => {
    incidentsApi.getDashboardSummary.mockRejectedValue({
      status: 500, detail: 'Internal server error',
    })
    renderWithProviders(<DashboardPage />, { as: 'employee' })

    expect(await screen.findByText('Internal server error')).toBeInTheDocument()
  })
})
