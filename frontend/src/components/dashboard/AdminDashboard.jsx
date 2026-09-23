import {
  Card, CardContent, Chip, Divider, Grid, List, ListItem, ListItemText, Stack, Typography,
} from '@mui/material'
import AccessTimeIcon from '@mui/icons-material/AccessTimeOutlined'
import AssignmentIcon from '@mui/icons-material/AssignmentOutlined'
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined'
import DescriptionIcon from '@mui/icons-material/DescriptionOutlined'
import PersonSearchIcon from '@mui/icons-material/PersonSearchOutlined'
import WarningIcon from '@mui/icons-material/WarningAmberOutlined'
import { Link } from 'react-router-dom'
import StatCard from '../StatCard'
import StatusChip from '../StatusChip'
import StatusCounts from './StatusCounts'
import { label } from '../../constants'

/**
 * What a facility admin sees: the whole site.
 *
 * Part of: frontend / dashboard.
 *
 * This is where most of the brief's business questions get answered — where
 * problems keep happening, how long things take, who is carrying the work, who
 * is free, and what is stuck and why. The other two dashboards are deliberately
 * narrower; this one is the reason the data is collected.
 */

// The tint behind each card's icon. Four cards of identical grey text get read
// left to right every time; a colour and a shape give each one a position you
// learn after a day. They repeat the meaning of the number rather than adding
// one — blue for a plain count, amber for something waiting, red for something
// wrong, green for something finished.
const TONE = {
  neutral: { bg: '#EFF8FF', fg: '#175CD3' },
  waiting: { bg: '#FFFAEB', fg: '#B54708' },
  problem: { bg: '#FEF3F2', fg: '#B42318' },
  done: { bg: '#ECFDF3', fg: '#027A48' },
}

export default function AdminDashboard({ summary }) {
  const byStatus = summary.counts_by_status || {}
  const byPriority = summary.counts_by_priority || {}
  const workload = summary.workload || []
  const availability = summary.engineer_availability || {}

  const total = Object.values(byStatus).reduce((sum, count) => sum + count, 0)
  const stillOpen = (byStatus.open || 0) + (byStatus.in_progress || 0) + (byStatus.blocked || 0)
  const unassigned = summary.unassigned_count || 0

  return (
    <Stack spacing={3}>
      <div>
        <Typography variant="h1">Dashboard</Typography>
        <Typography color="text.secondary">Every incident across all buildings.</Typography>
      </div>

      <Grid container spacing={2}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Total incidents" value={total}
                    icon={DescriptionIcon} tone={TONE.neutral} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Still open" value={stillOpen} caption="open, in progress or blocked"
                    icon={WarningIcon} tone={TONE.waiting} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Nobody assigned" value={unassigned} caption="waiting for an owner"
                    icon={PersonSearchIcon} tone={TONE.problem} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Requests to decide" value={summary.pending_assignment_requests}
                    caption="engineers asking for work"
                    icon={AssignmentIcon} tone={TONE.neutral} />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Avg hours to acknowledge"
                    value={summary.avg_hours_to_acknowledge ?? '—'}
                    caption="reported until work started"
                    icon={AccessTimeIcon} tone={TONE.neutral} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Avg hours to assign" value={summary.avg_hours_to_assign ?? '—'}
                    caption="reported until given to someone"
                    icon={AccessTimeIcon} tone={TONE.neutral} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Avg hours to resolve" value={summary.avg_hours_to_resolve ?? '—'}
                    caption="reported until resolved"
                    icon={CheckCircleIcon} tone={TONE.done} />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>By status</Typography>
              <StatusCounts counts={byStatus} />

              <Divider sx={{ my: 2 }} />

              <Typography variant="h2" gutterBottom>By priority</Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {Object.entries(byPriority).map(([priority, count]) => (
                  <Chip key={priority} label={`${label(priority)}: ${count}`} size="small" />
                ))}
                {Object.keys(byPriority).length === 0 && (
                  <Typography color="text.secondary">No incidents yet.</Typography>
                )}
              </Stack>

              <Divider sx={{ my: 2 }} />

              <Typography variant="h2" gutterBottom>By category</Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                {Object.entries(summary.category_breakdown || {}).map(([category, count]) => (
                  <Chip key={category} label={`${label(category)}: ${count}`} size="small" />
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>Where problems keep happening</Typography>
              {summary.top_locations.length === 0 ? (
                <Typography color="text.secondary">Nothing reported by location yet.</Typography>
              ) : (
                <List dense>
                  {summary.top_locations.map((location) => (
                    <ListItem key={location.building_id} disableGutters>
                      <ListItemText primary={location.name}
                                    secondary={`${location.count} incident${location.count === 1 ? '' : 's'}`} />
                    </ListItem>
                  ))}
                </List>
              )}

              <Divider sx={{ my: 2 }} />

              <Typography variant="h2" gutterBottom>Who is carrying the work</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Incidents per engineer, busiest first, plus how many have no owner.
              </Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mb: 2 }}>
                {workload.map((row) => (
                  <Chip key={row.engineer_id} size="small" label={`${row.name}: ${row.count}`} />
                ))}
                {unassigned > 0 && (
                  <Chip size="small" color="warning" label={`Unassigned: ${unassigned}`} />
                )}
                {workload.length === 0 && unassigned === 0 && (
                  <Typography color="text.secondary">Nothing assigned yet.</Typography>
                )}
              </Stack>

              <Typography variant="h2" gutterBottom>Who is free</Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Chip size="small" color="success" label={`Available: ${availability.available || 0}`} />
                <Chip size="small" color="warning" label={`Busy: ${availability.busy || 0}`} />
                <Chip size="small" label={`Off: ${availability.off || 0}`} />
              </Stack>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                Manage the rota on the <Link to="/engineers">Engineers</Link> page.
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Needs your attention</Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Escalated or blocked, with the reason given.
          </Typography>

          {summary.escalated_blocked.length === 0 ? (
            <Typography color="text.secondary">Nothing escalated or blocked.</Typography>
          ) : (
            <List>
              {summary.escalated_blocked.map((incident) => (
                <ListItem key={incident.id} disableGutters component={Link}
                          to={`/incidents/${incident.id}`}
                          sx={{ color: 'inherit', textDecoration: 'none' }}>
                  <ListItemText
                    primary={
                      <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                        <Typography>{incident.title}</Typography>
                        <StatusChip status={incident.status} />
                        <StatusChip priority={incident.priority} />
                        {incident.escalated && <Chip size="small" color="error" label="Escalated" />}
                      </Stack>
                    }
                    secondary={incident.blocked_reason || incident.escalation_reason || 'No reason given'}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </CardContent>
      </Card>
    </Stack>
  )
}
