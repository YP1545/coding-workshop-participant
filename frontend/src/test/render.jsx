/**
 * Rendering a component the way the app does.
 *
 * Part of: frontend / tests.
 *
 * Why its own file: almost every component here needs a theme, a router and a
 * signed-in user to render at all. Putting the providers in one helper keeps
 * each test about the thing it is testing, and lets a test say "render this as
 * an engineer" in one argument — which is exactly the axis most of the
 * behaviour turns on.
 */

import { ThemeProvider } from '@mui/material'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthContext } from '../auth/authContext'
import theme from '../theme'

/** A stand-in account for each role, matching what /auth/me returns. */
export const PEOPLE = {
  employee: {
    id: 'user-employee', email: 'sam.employee@acme.inc',
    full_name: 'Sam Rivera', role: 'employee',
  },
  engineer: {
    id: 'user-engineer', email: 'alex.engineer@acme.inc',
    full_name: 'Alex Chen', role: 'engineer',
  },
  admin: {
    id: 'user-admin', email: 'dana.admin@acme.inc',
    full_name: 'Dana Okafor', role: 'facility_admin',
  },
}

/**
 * Render a component inside the app's providers.
 *
 * @param {React.ReactElement} ui the component under test.
 * @param {object} [options]
 * @param {string|null} [options.as] a key of PEOPLE, or null for signed out.
 * @param {string} [options.route] the URL the router should start at.
 */
export function renderWithProviders(ui, { as = 'employee', route = '/' } = {}) {
  const user = as ? PEOPLE[as] : null

  const auth = {
    user,
    role: user ? user.role : null,
    isAdmin: user ? user.role === 'facility_admin' : false,
    isEngineer: user ? user.role === 'engineer' : false,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  }

  return {
    auth,
    ...render(
      <ThemeProvider theme={theme}>
        <MemoryRouter initialEntries={[route]}>
          <AuthContext.Provider value={auth}>{ui}</AuthContext.Provider>
        </MemoryRouter>
      </ThemeProvider>,
    ),
  }
}
