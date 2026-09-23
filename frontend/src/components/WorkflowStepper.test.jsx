/**
 * Tests for the workflow stepper.
 *
 * Part of: frontend / tests.
 *
 * This component is the brief's "visual representation of the ticket workflow",
 * and the case worth pinning down is blocked: it is not a fifth step, it is a
 * marker on the step the incident will return to.
 */

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import WorkflowStepper from './WorkflowStepper'
import { renderWithProviders } from '../test/render'

function incident(overrides) {
  return {
    id: 'incident-1', title: 'Broken chair', status: 'open',
    blocked_reason: null, ...overrides,
  }
}

describe('WorkflowStepper', () => {
  it('shows the four steps of the normal path', () => {
    renderWithProviders(<WorkflowStepper incident={incident({})} />)

    for (const step of ['Open', 'In progress', 'Resolved', 'Closed']) {
      expect(screen.getByText(step)).toBeInTheDocument()
    }
  })

  it('does not put blocked in the line of steps', () => {
    renderWithProviders(<WorkflowStepper incident={incident({
      status: 'blocked', blocked_reason: 'Waiting on a part',
    })} />)

    // "Blocked:" appears in the alert beneath, but never as a step label.
    const steps = screen.getAllByText(/^(Open|In progress|Resolved|Closed)$/)
    expect(steps).toHaveLength(4)
  })

  it('explains why a blocked incident is stuck', () => {
    renderWithProviders(<WorkflowStepper incident={incident({
      status: 'blocked', blocked_reason: 'Waiting on the replacement access point',
    })} />)

    expect(screen.getByText(/Waiting on the replacement access point/)).toBeInTheDocument()
  })

  it('says so when a blocked incident has no reason recorded', () => {
    renderWithProviders(<WorkflowStepper incident={incident({
      status: 'blocked', blocked_reason: null,
    })} />)

    expect(screen.getByText(/no reason given/)).toBeInTheDocument()
  })

  it('shows no alert when nothing is blocked', () => {
    renderWithProviders(<WorkflowStepper incident={incident({ status: 'resolved' })} />)

    expect(screen.queryByText(/Blocked:/)).not.toBeInTheDocument()
  })
})
