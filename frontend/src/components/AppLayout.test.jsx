/**
 * Tests for the app frame and its navigation.
 *
 * Part of: frontend / tests.
 *
 * The navigation is built from the signed-in role, so these check that nobody
 * is offered a door that will not open for them. The number of links also
 * decides when the bar collapses to a menu — an admin has seven and needs a
 * wide screen, which is what broke the layout at tablet width.
 */

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AppLayout from './AppLayout'
import { renderWithProviders } from '../test/render'

/** The links a role should be offered, in the bar or behind the menu. */
function linkNames() {
  return screen.getAllByRole('link').map((link) => link.textContent)
}

describe('AppLayout', () => {
  it('offers an employee only what they can open', () => {
    renderWithProviders(<AppLayout />, { as: 'employee' })

    const links = linkNames()
    expect(links).toContain('Incidents')
    expect(links).toContain('Profile')
    expect(links).not.toContain('Facilities')
    expect(links).not.toContain('People')
    expect(links).not.toContain('Engineers')
  })

  it('sends an engineer to their own requests, not the roster', () => {
    renderWithProviders(<AppLayout />, { as: 'engineer' })

    const links = linkNames()
    expect(links).toContain('My requests')
    expect(links).not.toContain('Engineers')
    expect(links).not.toContain('People')
  })

  it('gives an admin the management pages', () => {
    renderWithProviders(<AppLayout />, { as: 'admin' })

    const links = linkNames()
    for (const page of ['Incidents', 'Requests', 'Facilities', 'People', 'Engineers']) {
      expect(links).toContain(page)
    }
  })

  it('offers a signed-out visitor a way in and nothing else', () => {
    renderWithProviders(<AppLayout />, { as: null })

    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument()
    expect(linkNames()).not.toContain('Incidents')
  })

  it('shows an admin more links than an employee, which is why the bar collapses sooner', () => {
    const { unmount } = renderWithProviders(<AppLayout />, { as: 'employee' })
    const employeeLinks = linkNames().length
    unmount()

    renderWithProviders(<AppLayout />, { as: 'admin' })

    expect(linkNames().length).toBeGreaterThan(employeeLinks)
  })
})
