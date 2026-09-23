import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, Divider, MenuItem, Stack, TextField, Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import * as incidentsApi from '../api/incidentsApi'
import ErrorMessage from '../components/ErrorMessage'
import StatusChip from '../components/StatusChip'
import { formatDate, label } from '../constants'

/**
 * The admin's queue of engineers asking for work.
 *
 * Part of: frontend / assignment requests (admin).
 *
 * Each card shows who is asking and what the job is, because that is the whole
 * decision. The backend sends the engineer's name and the incident alongside
 * the request, so this page needs one call rather than one per row.
 *
 * Approving does three things on the server at once — records the decision,
 * assigns the incident, and denies everyone else who asked — so this only has
 * to send one request and reload.
 */
export default function AssignmentRequestsPage() {
  const navigate = useNavigate()

  const [requests, setRequests] = useState([])
  const [status, setStatus] = useState('pending')
  const [error, setError] = useState(null)

  function load() {
    incidentsApi.listAllRequests(status).then(setRequests).catch((err) => setError(err))
  }

  useEffect(load, [status])

  async function decide(requestId, decision) {
    setError(null)
    try {
      await incidentsApi.decideRequest(requestId, decision)
      load()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">Assignment requests</Typography>
        <Typography color="text.secondary">
          Engineers asking to be given an unassigned incident.
        </Typography>
      </Box>

      <ErrorMessage error={error} />

      <TextField select size="small" label="Show" value={status} sx={{ maxWidth: 220 }}
                 onChange={(event) => setStatus(event.target.value)}>
        <MenuItem value="pending">Pending</MenuItem>
        <MenuItem value="approved">Approved</MenuItem>
        <MenuItem value="denied">Denied</MenuItem>
      </TextField>

      {requests.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">Nothing {label(status).toLowerCase()}.</Typography>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={2}>
          {requests.map((item) => (
            <Card key={item.id}>
              <CardContent>
                <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'baseline', flexWrap: 'wrap' }}>
                  <Typography variant="h6" component="h2">
                    {item.engineer_name || 'An engineer'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {item.engineer_email}
                  </Typography>
                </Stack>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  asked {formatDate(item.requested_at)}
                  {item.decided_at && ` · decided ${formatDate(item.decided_at)}`}
                </Typography>

                <Divider sx={{ my: 2 }} />

                {item.incident ? (
                  <Box sx={{ cursor: 'pointer' }}
                       onClick={() => navigate(`/incidents/${item.incident_id}`)}>
                    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mb: 1 }} useFlexGap>
                      <StatusChip status={item.incident.status} />
                      <StatusChip priority={item.incident.priority} />
                    </Stack>
                    <Typography variant="subtitle1">{item.incident.title}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {label(item.incident.category)} · reported {formatDate(item.incident.created_at)}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {item.incident.description}
                    </Typography>
                  </Box>
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    That incident has since been deleted.
                  </Typography>
                )}

                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 2 }}>
                  {item.status === 'pending' ? (
                    <>
                      <Button variant="contained" size="small"
                              onClick={() => decide(item.id, 'approved')}>
                        Approve
                      </Button>
                      <Button size="small" onClick={() => decide(item.id, 'denied')}>
                        Deny
                      </Button>
                    </>
                  ) : (
                    <Typography variant="body2">
                      <strong>{label(item.status)}</strong>
                    </Typography>
                  )}
                  <Box sx={{ flexGrow: 1 }} />
                  <Button size="small" onClick={() => navigate(`/incidents/${item.incident_id}`)}>
                    Open incident
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
