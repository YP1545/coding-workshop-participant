import { Alert, Button, Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material'
import AssignmentIcon from '@mui/icons-material/AssignmentOutlined'
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined'
import HourglassIcon from '@mui/icons-material/HourglassEmptyOutlined'
import WarningIcon from '@mui/icons-material/WarningAmberOutlined'
import { Link } from 'react-router-dom'
import IncidentMiniList from './IncidentMiniList'
import StatCard from '../StatCard'
import StatusCounts from './StatusCounts'
import { label } from '../../constants'

/**
 * What an engineer sees: their workload, and what they could pick up.
 *
 * Part of: frontend / dashboard.
 *
 * The counts cover work actually assigned to them. Unassigned incidents they
 * are allowed to browse are shown separately as an opportunity, not folded
 * into their queue — otherwise their own workload would look bigger than it is
 * every time somebody else reported something.
 */
// See AdminDashboard for why the icons are tinted: a colour and a shape give
// each card a position you learn, rather than four blocks of identical grey.
const TONE = {
  neutral: { bg: '#EFF8FF', fg: '#175CD3' },
  waiting: { bg: '#FFFAEB', fg: '#B54708' },
  done: { bg: '#ECFDF3', fg: '#027A48' },
}

export default function EngineerDashboard({ summary, user }) {
  const byStatus = summary.counts_by_status || {}
  const byPriority = summary.counts_by_priority || {}
  const assigned = summary.assigned_incidents || []
  const total = Object.values(byStatus).reduce((sum, count) => sum + count, 0)

  return (
    <Stack spacing={3}>
      <div>
        <Typography variant="h1">Your work</Typography>
        <Typography color="text.secondary">
          Signed in as {user.full_name}. Incidents assigned to you.
        </Typography>
      </div>

      {summary.needs_profile && (
        <Alert severity="warning">
          You have the engineer role but no engineer profile yet, so nothing can be
          assigned to you. A facility admin can set that up from the People page.
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Assigned to you" value={total}
                    icon={AssignmentIcon} tone={TONE.neutral} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Still to do" value={summary.active_count}
                    icon={WarningIcon} tone={TONE.waiting}
                    caption="open, in progress or blocked" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard title="Requests pending" value={summary.my_pending_requests}
                    icon={HourglassIcon} tone={TONE.waiting}
                    caption="waiting on an admin" />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <StatCard icon={CheckCircleIcon} tone={TONE.done}
                    title="Your avg hours to resolve"
                    value={summary.avg_hours_to_resolve ?? '—'}
                    caption="reported until you resolved it" />
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Assigned to you</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Still needing work, newest first.
            {summary.active_count > assigned.length &&
              ` Showing ${assigned.length} of ${summary.active_count}.`}
          </Typography>
          <IncidentMiniList incidents={assigned}
                            emptyText="Nothing assigned to you right now." />
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>Your incidents by status</Typography>
              <StatusCounts counts={byStatus} />
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mt: 2 }}>
                {Object.entries(byPriority).map(([priority, count]) => (
                  <Chip key={priority} size="small" label={`${label(priority)}: ${count}`} />
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>Work you could take</Typography>
              <Typography variant="h4" component="p" sx={{ mb: 1 }}>
                {summary.open_to_request}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Open incidents with nobody assigned. Open one and use
                <strong> Request assignment</strong>; an admin decides.
              </Typography>
              <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                <Button variant="contained" component={Link} to="/incidents?status=open">
                  Browse open work
                </Button>
                <Button component={Link} to="/my-requests">
                  My requests ({summary.my_pending_requests})
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  )
}
