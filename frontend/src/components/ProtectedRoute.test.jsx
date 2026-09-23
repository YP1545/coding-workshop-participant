/**
 * Tests for the route guard.
 *
 * Part of: frontend / tests.
 *
 * The guard is a courtesy, not the security boundary — the API refuses the same
 * things again. What it must get right is not flashing the login page at
 * somebody who is actually signed in while their stored token is being checked.
 */

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { renderWithProviders } from '../test/render'

function guarded(roles) {
  return (
    <Routes>
      <Route path="/" element={
        <ProtectedRoute roles={roles}><div>The protected page</div></ProtectedRoute>} />
      <Route path="/login" element={<div>The login page</div>} />
    </Routes>
  )
}

describe('ProtectedRoute', () => {
  it('shows the page to somebody signed in', () => {
    renderWithProviders(guarded(), { as: 'employee' })

    expect(screen.getByText('The protected page')).toBeInTheDocument()
  })

  it('sends somebody signed out to the login page', () => {
    renderWithProviders(guarded(), { as: null })

    expect(screen.getByText('The login page')).toBeInTheDocument()
  })

  it('shows an admin page to an admin', () => {
    renderWithProviders(guarded(['facility_admin']), { as: 'admin' })

    expect(screen.getByText('The protected page')).toBeInTheDocument()
  })

  it('turns away a signed-in person with the wrong role', () => {
    renderWithProviders(guarded(['facility_admin']), { as: 'engineer' })

    expect(screen.queryByText('The protected page')).not.toBeInTheDocument()
  })

  it('does not accept an engineer on an engineer-only page when signed in as an employee', () => {
    renderWithProviders(guarded(['engineer']), { as: 'employee' })

    expect(screen.queryByText('The protected page')).not.toBeInTheDocument()
  })
})
