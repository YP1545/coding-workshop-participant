import {
  Box, Card, Link as MuiLink, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from '@mui/material'
import { Link } from 'react-router-dom'
import { useMediaQuery } from 'react-responsive'
import StatusChip from './StatusChip'
import { label, timeAgo } from '../constants'

/**
 * A list of incidents: a table on a wide screen, stacked cards on a narrow one.
 *
 * Part of: frontend / incidents.
 *
 * Why two shapes rather than one scrollable table: a six-column table at phone
 * width either overflows sideways or squeezes every column to two words. Apple's
 * guidance is explicit that primary content should be readable without scrolling
 * horizontally (https://developer.apple.com/design/tips/), so below the
 * breakpoint the same rows are stacked instead — same data, no side-scrolling.
 *
 * @param {object[]} incidents Rows from GET /incidents.
 * @param {Object<string,string>} [buildingNames] Building id to name, when the
 *   caller has already loaded them. Missing ids simply show a dash.
 * @param {Object<string,string>} [assigneeNames] Engineer profile id to name.
 */
export default function IncidentTable({ incidents, buildingNames = {}, assigneeNames = {} }) {
  // Six columns need roughly this much room before they start to crowd.
  const isNarrow = useMediaQuery({ maxWidth: 900 })

  if (!incidents || incidents.length === 0) return null

  if (isNarrow) {
    return (
      <Stack spacing={1.5}>
        {incidents.map((incident) => (
          <Card key={incident.id} sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} useFlexGap
                   sx={{ mb: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <StatusChip status={incident.status} />
              <StatusChip priority={incident.priority} />
              {incident.escalated && <StatusChip status="blocked" />}
            </Stack>

            <MuiLink component={Link} to={`/incidents/${incident.id}`}
                     sx={{ display: 'block', mb: 0.5 }}>
              {incident.reference}
            </MuiLink>
            <Typography sx={{ fontWeight: 600 }}>{incident.title}</Typography>

            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {label(incident.category)}
              {buildingNames[incident.building_id] && ` · ${buildingNames[incident.building_id]}`}
              {` · updated ${timeAgo(incident.updated_at)}`}
            </Typography>
          </Card>
        ))}
      </Stack>
    )
  }

  return (
    <TableContainer component={Card}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Incident</TableCell>
            <TableCell>Building</TableCell>
            <TableCell>Priority</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Assignee</TableCell>
            <TableCell>Updated</TableCell>
          </TableRow>
        </TableHead>

        <TableBody>
          {incidents.map((incident) => (
            <TableRow key={incident.id} hover>
              <TableCell>
                {/* Two lines: the short handle people say out loud, and the
                    title they actually recognise the incident by. */}
                <MuiLink component={Link} to={`/incidents/${incident.id}`}>
                  {incident.reference}
                </MuiLink>
                <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 380 }}>
                  {incident.title}
                </Typography>
              </TableCell>

              <TableCell>{buildingNames[incident.building_id] || '—'}</TableCell>

              <TableCell><StatusChip priority={incident.priority} /></TableCell>

              <TableCell>
                <Stack direction="row" spacing={0.5} useFlexGap
                       sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  <StatusChip status={incident.status} />
                  {incident.escalated && (
                    <Box component="span" sx={{ fontSize: '0.75rem', color: '#B42318',
                                                fontWeight: 600 }}>
                      Escalated
                    </Box>
                  )}
                </Stack>
              </TableCell>

              <TableCell>
                {incident.assignee_id
                  ? assigneeNames[incident.assignee_id] || 'Assigned'
                  : <Typography variant="body2" color="text.secondary">Unassigned</Typography>}
              </TableCell>

              <TableCell>
                <Typography variant="body2" color="text.secondary">
                  {timeAgo(incident.updated_at)}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
