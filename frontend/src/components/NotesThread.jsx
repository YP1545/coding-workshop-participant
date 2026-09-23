import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, Divider, Stack, TextField, Typography,
} from '@mui/material'
import * as incidentsApi from '../api/incidentsApi'
import ErrorMessage from './ErrorMessage'
import { formatDate } from '../constants'

/**
 * The conversation on an incident.
 *
 * Part of: frontend / incidents.
 *
 * With no email or Slack integration in this version, this thread plus the
 * status stepper is how someone finds out what is happening to the problem
 * they reported. That makes it more important than it looks.
 *
 * @param {boolean} canComment Whether to show the form. An engineer browsing an
 *   unassigned incident can read the thread to decide whether to ask for the
 *   job, but the server will refuse a note from them — so offering the box
 *   would only produce an error they could not have predicted.
 */
export default function NotesThread({ incidentId, canComment = true }) {
  const [notes, setNotes] = useState([])
  const [body, setBody] = useState('')
  const [error, setError] = useState(null)
  const [posting, setPosting] = useState(false)

  // Same refresh-counter idea as the detail page: posting a note bumps it, and
  // the effect fetches the thread again.
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    incidentsApi.listNotes(incidentId).then(setNotes).catch((err) => setError(err))
  }, [incidentId, refreshKey])

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setPosting(true)

    try {
      await incidentsApi.addNote(incidentId, body)
      setBody('')
      setRefreshKey((current) => current + 1)
    } catch (err) {
      setError(err)
    } finally {
      setPosting(false)
    }
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h2" gutterBottom>Notes</Typography>

        <ErrorMessage error={error} />

        {notes.length === 0 ? (
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            Nothing has been said yet.
          </Typography>
        ) : (
          <Stack spacing={2} sx={{ mb: 2 }}>
            {notes.map((note) => (
              <Box key={note.id}>
                <Typography variant="caption" color="text.secondary">
                  {formatDate(note.created_at)}
                </Typography>
                <Typography sx={{ whiteSpace: 'pre-wrap' }}>{note.body}</Typography>
                <Divider sx={{ mt: 1 }} />
              </Box>
            ))}
          </Stack>
        )}

        {canComment ? (
          <Stack spacing={2} component="form" onSubmit={handleSubmit}>
            <TextField label="Add a note" value={body} multiline rows={2} fullWidth
                       onChange={(event) => setBody(event.target.value)} />
            <Box>
              <Button type="submit" variant="contained" disabled={!body.trim() || posting}>
                {posting ? 'Posting…' : 'Post note'}
              </Button>
            </Box>
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            Only the person who reported this, the engineer it is assigned to, and
            facility admins can add notes.
          </Typography>
        )}
      </CardContent>
    </Card>
  )
}
