/**
 * Tests for the note thread.
 *
 * Part of: frontend / tests.
 *
 * The rule under test: an engineer looking at work they have not been given can
 * read the thread but not write in it. The server refuses such a note with a
 * 403, so offering the box would only produce an error nobody could have
 * predicted — the form has to be absent, and the reason has to be stated.
 */

import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NotesThread from './NotesThread'
import * as incidentsApi from '../api/incidentsApi'
import { renderWithProviders } from '../test/render'

vi.mock('../api/incidentsApi')

describe('NotesThread', () => {
  beforeEach(() => {
    incidentsApi.listNotes.mockResolvedValue([
      { id: 'note-1', incident_id: 'incident-1', author_id: 'user-engineer',
        body: 'Part ordered.', created_at: '2026-09-22T10:00:00+00:00' },
    ])
    incidentsApi.addNote.mockResolvedValue({ id: 'note-2' })
  })

  it('shows the notes already on the incident', async () => {
    renderWithProviders(<NotesThread incidentId="incident-1" />)

    expect(await screen.findByText('Part ordered.')).toBeInTheDocument()
  })

  it('lets somebody who may comment post a note', async () => {
    renderWithProviders(<NotesThread incidentId="incident-1" canComment />)
    await screen.findByText('Part ordered.')

    await userEvent.type(screen.getByLabelText('Add a note'), 'Thanks for the update')
    await userEvent.click(screen.getByRole('button', { name: /post note/i }))

    await waitFor(() => {
      expect(incidentsApi.addNote).toHaveBeenCalledWith('incident-1', 'Thanks for the update')
    })
  })

  it('hides the form from somebody the server would refuse', async () => {
    renderWithProviders(<NotesThread incidentId="incident-1" canComment={false} />)
    await screen.findByText('Part ordered.')

    expect(screen.queryByLabelText('Add a note')).not.toBeInTheDocument()
    expect(screen.getByText(/Only the person who reported this/)).toBeInTheDocument()
  })

  it('cannot post an empty note', async () => {
    renderWithProviders(<NotesThread incidentId="incident-1" canComment />)
    await screen.findByText('Part ordered.')

    expect(screen.getByRole('button', { name: /post note/i })).toBeDisabled()
  })
})
