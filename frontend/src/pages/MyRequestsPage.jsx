import { useEffect, useState } from 'react'
import { Box, Card, CardContent, Stack, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import * as incidentsApi from '../api/incidentsApi'
import ErrorMessage from '../components/ErrorMessage'
import StatusChip from '../components/StatusChip'
import { formatDate, label } from '../constants'

/**
 * The jobs this engineer has asked for, and what came of them.
 *
 * Part of: frontend / assignment requests (engineer).
 *
 * The admin has their own queue of every request; this is the other side of it,
 * so an engineer can see what they are still waiting on without having to open
 * each incident.
 */
export default function MyRequestsPage() {
  const [requests, setRequests] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    incidentsApi.listMyRequests().then(setRequests).catch((err) => setError(err))
  }, [])

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">My requests</Typography>
        <Typography color="text.secondary">
          Incidents you have asked to be assigned to.
        </Typography>
      </Box>

      <ErrorMessage error={error} />

      {requests.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">
              You have not asked for any incidents yet. Open an unassigned
              incident and use <strong>Request assignment</strong>.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={2}>
          {requests.map((item) => (
            <Card key={item.id}>
              <CardContent>
                <Stack direction="row" spacing={2} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography>
                      <Link to={`/incidents/${item.incident_id}`}>
                        {item.incident ? item.incident.title : 'View the incident'}
                      </Link>
                    </Typography>
                    {item.incident && (
                      <Typography variant="body2" color="text.secondary">
                        {label(item.incident.category)} · {label(item.incident.status)}
                      </Typography>
                    )}
                    <Typography variant="body2" color="text.secondary">
                      Asked {formatDate(item.requested_at)}
                      {item.decided_at && ` · decided ${formatDate(item.decided_at)}`}
                    </Typography>
                  </Box>
                  <StatusChip
                    status={
                      item.status === 'approved' ? 'resolved'
                        : item.status === 'denied' ? 'closed' : 'open'
                    }
                  />
                  <Typography variant="body2">{label(item.status)}</Typography>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
