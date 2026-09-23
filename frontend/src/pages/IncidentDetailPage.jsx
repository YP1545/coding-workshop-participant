import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, CircularProgress, Divider, Grid, MenuItem,
  Stack, TextField, Typography,
} from '@mui/material'
import { useNavigate, useParams } from 'react-router-dom'
import * as engineersApi from '../api/engineersApi'
import * as incidentsApi from '../api/incidentsApi'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'
import NotesThread from '../components/NotesThread'
import StatusChip from '../components/StatusChip'
import WorkflowStepper from '../components/WorkflowStepper'
import { STATUSES, formatDate, label } from '../constants'

/**
 * One incident: where it has got to, what was said about it, and what this
 * person is allowed to do next.
 *
 * Part of: frontend / incidents.
 *
 * Every action panel below is shown only to the role that may use it, and the
 * backend checks the same rules again. Hiding a button is a courtesy; the
 * server refusing the request is the actual protection.
 */
export default function IncidentDetailPage() {
  const { incidentId } = useParams()
  const navigate = useNavigate()
  const { user, isAdmin, isEngineer } = useAuth()

  const [incident, setIncident] = useState(null)
  const [engineers, setEngineers] = useState([])
  const [requests, setRequests] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const [newStatus, setNewStatus] = useState('')
  const [blockedReason, setBlockedReason] = useState('')
  const [assignee, setAssignee] = useState('')
  const [escalationReason, setEscalationReason] = useState('')

  // Bumped after any action. The effects below depend on it, so raising it
  // refetches everything — simpler than each button knowing which pieces of
  // the page its change affected.
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    incidentsApi
      .getIncident(incidentId)
      .then((data) => {
        setIncident(data)
        setAssignee(data.assignee_id || '')
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [incidentId, refreshKey])

  // Loaded for engineers as well as admins. An admin needs the list to choose
  // an assignee; an engineer needs it to find their own profile id, because
  // incidents are assigned to a profile rather than to an account. Without it,
  // an engineer could not tell that a job was theirs — which silently hid both
  // the status panel and the note box on their own work.
  useEffect(() => {
    if (!isAdmin && !isEngineer) return
    engineersApi.listEngineers().then(setEngineers).catch(() => setEngineers([]))
  }, [isAdmin, isEngineer, refreshKey])

  useEffect(() => {
    if (!isAdmin && !isEngineer) return
    incidentsApi.listRequestsForIncident(incidentId).then(setRequests).catch(() => setRequests([]))
  }, [incidentId, isAdmin, isEngineer, refreshKey])

  /**
   * Run an API call, then refetch so the screen matches the server.
   *
   * Refetching rather than patching the local copy: the server may have changed
   * more than we asked for — approving an assignment request also assigns the
   * incident and denies the other requests.
   */
  async function run(action) {
    setError(null)
    try {
      await action()
      setRefreshKey((current) => current + 1)
    } catch (err) {
      setError(err)
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!incident) return <ErrorMessage error={error} />

  const isReporter = incident.reporter_id === user.id
  const myProfile = engineers.find((engineer) => engineer.user_id === user.id)
  const isAssignedToMe = isEngineer && incident.assignee_id && incident.assignee_id === (myProfile && myProfile.id)
  const canChangeStatus = isAdmin || isAssignedToMe
  const canRequestIt = isEngineer && !incident.assignee_id
  // Mirrors access.can_comment_on on the server: reporter, assigned engineer,
  // or admin. An engineer looking at work they have not been given can read the
  // thread but not write in it.
  const canComment = isAdmin || isReporter || isAssignedToMe

  return (
    <Stack spacing={3}>
      <Box>
        <Button onClick={() => navigate('/incidents')} sx={{ mb: 1 }}>← All incidents</Button>
        {/* The number goes above the title, because it is what somebody
            reads out when they ring up about this incident. */}
        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
          {incident.reference}
        </Typography>
        <Typography variant="h1">{incident.title}</Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mt: 1 }} useFlexGap>
          <StatusChip status={incident.status} />
          <StatusChip priority={incident.priority} />
          {incident.escalated && <StatusChip status="blocked" />}
        </Stack>
      </Box>

      <ErrorMessage error={error} />

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Progress</Typography>
          <WorkflowStepper incident={incident} />
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>Details</Typography>
              <Typography sx={{ whiteSpace: 'pre-wrap', mb: 2 }}>{incident.description}</Typography>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={0.5}>
                <Typography variant="body2"><strong>Category:</strong> {label(incident.category)}</Typography>
                <Typography variant="body2"><strong>Reported:</strong> {formatDate(incident.created_at)}</Typography>
                <Typography variant="body2"><strong>Work started:</strong> {formatDate(incident.acknowledged_at)}</Typography>
                <Typography variant="body2"><strong>Assigned:</strong> {formatDate(incident.assigned_at)}</Typography>
                <Typography variant="body2"><strong>Resolved:</strong> {formatDate(incident.resolved_at)}</Typography>
                <Typography variant="body2"><strong>Closed:</strong> {formatDate(incident.closed_at)}</Typography>
                {incident.escalation_reason && (
                  <Typography variant="body2">
                    <strong>Escalation reason:</strong> {incident.escalation_reason}
                  </Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 5 }}>
          <Stack spacing={2}>
            {canChangeStatus && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Update status</Typography>
                  <Stack spacing={2}>
                    <TextField select size="small" label="Move to" value={newStatus} fullWidth
                               onChange={(event) => setNewStatus(event.target.value)}>
                      {STATUSES.filter((status) => status !== incident.status).map((status) => (
                        <MenuItem key={status} value={status}>{label(status)}</MenuItem>
                      ))}
                    </TextField>

                    {newStatus === 'blocked' && (
                      <TextField size="small" label="Why is it blocked?" fullWidth required
                                 value={blockedReason}
                                 onChange={(event) => setBlockedReason(event.target.value)} />
                    )}

                    <Button variant="contained" disabled={!newStatus}
                            onClick={() => run(async () => {
                              await incidentsApi.changeStatus(incident.id, newStatus, blockedReason)
                              setNewStatus('')
                              setBlockedReason('')
                            })}>
                      Update
                    </Button>
                    <Typography variant="caption" color="text.secondary">
                      Not every move is allowed — the server will say so if this one is not.
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            )}

            {isAdmin && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Assign</Typography>
                  <Stack spacing={2}>
                    <TextField select size="small" label="Engineer" value={assignee} fullWidth
                               onChange={(event) => setAssignee(event.target.value)}>
                      <MenuItem value="">Nobody</MenuItem>
                      {engineers.map((engineer) => (
                        <MenuItem key={engineer.id} value={engineer.id}>
                          {engineer.full_name} ({label(engineer.availability)})
                        </MenuItem>
                      ))}
                    </TextField>
                    <Button variant="contained"
                            onClick={() => run(() => incidentsApi.assignIncident(incident.id, assignee || null))}>
                      Save assignment
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
            )}

            {isReporter && !incident.escalated && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Ask for escalation</Typography>
                  <Stack spacing={2}>
                    <TextField size="small" label="Why does this need escalating?" fullWidth
                               multiline rows={2} value={escalationReason}
                               onChange={(event) => setEscalationReason(event.target.value)} />
                    <Button variant="outlined" disabled={!escalationReason}
                            onClick={() => run(async () => {
                              await incidentsApi.requestEscalation(incident.id, escalationReason)
                              setEscalationReason('')
                            })}>
                      {incident.escalation_requested ? 'Update request' : 'Request escalation'}
                    </Button>
                    {incident.escalation_requested && (
                      <Typography variant="caption" color="text.secondary">
                        Requested. A facility admin will decide.
                      </Typography>
                    )}
                  </Stack>
                </CardContent>
              </Card>
            )}

            {isAdmin && incident.escalation_requested && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Escalation requested</Typography>
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    {incident.escalation_reason || 'No reason given.'}
                  </Typography>
                  <Button variant="contained" color={incident.escalated ? 'inherit' : 'error'}
                          onClick={() => run(() => incidentsApi.setEscalated(incident.id, !incident.escalated))}>
                    {incident.escalated ? 'Withdraw escalation' : 'Confirm escalation'}
                  </Button>
                </CardContent>
              </Card>
            )}

            {canRequestIt && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Take this job</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Nobody is assigned. Ask an admin to give it to you.
                  </Typography>
                  <Button variant="contained"
                          onClick={() => run(() => incidentsApi.requestAssignment(incident.id))}>
                    Request assignment
                  </Button>
                </CardContent>
              </Card>
            )}

            {isAdmin && requests.length > 0 && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Assignment requests</Typography>
                  <Stack spacing={2}>
                    {requests.map((item) => (
                      <Box key={item.id}>
                        <Typography variant="body2">
                          <strong>{item.engineer_name || 'An engineer'}</strong> — {label(item.status)}
                        </Typography>
                        {item.engineer_email && (
                          <Typography variant="caption" color="text.secondary">
                            {item.engineer_email}
                          </Typography>
                        )}
                        {item.status === 'pending' && (
                          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                            <Button size="small" variant="contained"
                                    onClick={() => run(() => incidentsApi.decideRequest(item.id, 'approved'))}>
                              Approve
                            </Button>
                            <Button size="small"
                                    onClick={() => run(() => incidentsApi.decideRequest(item.id, 'denied'))}>
                              Deny
                            </Button>
                          </Stack>
                        )}
                      </Box>
                    ))}
                  </Stack>
                </CardContent>
              </Card>
            )}

            {isAdmin && (
              <Card>
                <CardContent>
                  <Typography variant="h2" gutterBottom>Danger zone</Typography>
                  <Button color="error" variant="outlined"
                          onClick={() => run(async () => {
                            await incidentsApi.deleteIncident(incident.id)
                            navigate('/incidents')
                          })}>
                    Delete incident
                  </Button>
                </CardContent>
              </Card>
            )}
          </Stack>
        </Grid>
      </Grid>

      <NotesThread incidentId={incident.id} canComment={canComment} />
    </Stack>
  )
}
