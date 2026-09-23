/**
 * Tests for the sign-in page.
 *
 * Part of: frontend / tests.
 *
 * The case that matters is the failure: when the server refuses, the person has
 * to be told what it said and the form has to stay usable. A login form that
 * silently does nothing on a wrong password is the most frustrating bug in any
 * app.
 */

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import LoginPage from './LoginPage'
import { renderWithProviders } from '../test/render'

describe('LoginPage', () => {
  it('signs in with what was typed', async () => {
    const { auth } = renderWithProviders(<LoginPage />, { as: null })
    auth.login.mockResolvedValue({})

    await userEvent.type(screen.getByLabelText(/email/i), 'sam.employee@acme.inc')
    await userEvent.type(screen.getByLabelText(/password/i), 'LocalDev!2026')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(auth.login).toHaveBeenCalledWith('sam.employee@acme.inc', 'LocalDev!2026')
    })
  })

  it('shows the message the server gave when sign-in fails', async () => {
    const { auth } = renderWithProviders(<LoginPage />, { as: null })
    auth.login.mockRejectedValue({ status: 401, detail: 'Invalid email or password' })

    await userEvent.type(screen.getByLabelText(/email/i), 'sam.employee@acme.inc')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument()
  })

  it('leaves the form usable after a failure', async () => {
    const { auth } = renderWithProviders(<LoginPage />, { as: null })
    auth.login.mockRejectedValue({ status: 401, detail: 'Invalid email or password' })

    await userEvent.type(screen.getByLabelText(/email/i), 'sam.employee@acme.inc')
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
    await screen.findByText('Invalid email or password')

    expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled()
  })

  it('tells people the address has to be a company one', () => {
    renderWithProviders(<LoginPage />, { as: null })

    expect(screen.getByText(/@acme\.inc/)).toBeInTheDocument()
  })
})
