import { Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material'
import DescriptionIcon from '@mui/icons-material/DescriptionOutlined'
import MarkChatUnreadIcon from '@mui/icons-material/MarkChatUnreadOutlined'
import WarningIcon from '@mui/icons-material/WarningAmberOutlined'
import IncidentMiniList from './IncidentMiniList'
import StatCard from '../StatCard'
import StatusCounts from './StatusCounts'
import { label } from '../../constants'

/**
 * What an employee sees: their own tickets, and which ones have news.
 *
 * Part of: frontend / dashboard.
 *
 * No site-wide figures. A league table of problem buildings is not an
 * employee's question, and the server does not send them the data either.
 *
 * "Waiting on you" is this product's answer to "how effectively are employees
 * informed". There is no email or Slack integration, so instead of a
 * notification that might be missed, the dashboard is simply correct every
 * time they look at it.
 */
// See AdminDashboard for why the icons are tinted: a colour and a shape give
// each card a position you learn, rather than four blocks of identical grey.
const TONE = {
  neutral: { bg: '#EFF8FF', fg: '#175CD3' },
  waiting: { bg: '#FFFAEB', fg: '#B54708' },
  done: { bg: '#ECFDF3', fg: '#027A48' },
}

export default function EmployeeDashboard({ summary, user }) {
  const byStatus = summary.counts_by_status || {}
  const byPriority = summary.counts_by_priority || {}
  const total = Object.values(byStatus).reduce((sum, count) => sum + count, 0)
  const stillOpen = (byStatus.open || 0) + (byStatus.in_progress || 0) + (byStatus.blocked || 0)
  const waiting = summary.awaiting_your_attention || []

  return (
    <Stack spacing={3}>
      <div>
        <Typography variant="h1">Your incidents</Typography>
        <Typography color="text.secondary">
          Signed in as {user.full_name}. Everything here is what you reported.
        </Typography>
      </div>

      <Grid container spacing={2}>
        <Grid size={{ xs: 6, md: 4 }}>
          <StatCard title="Reported by you" value={total}
                    icon={DescriptionIcon} tone={TONE.neutral} />
        </Grid>
        <Grid size={{ xs: 6, md: 4 }}>
          <StatCard title="Still open" value={stillOpen} caption="open, in progress or blocked"
                    icon={WarningIcon} tone={TONE.waiting} />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <StatCard title="Waiting on you" value={summary.awaiting_count}
                    icon={MarkChatUnreadIcon} tone={TONE.waiting}
                    caption="someone replied since you last wrote" />
        </Grid>
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Waiting on you</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            The last note on these came from someone else.
            {summary.awaiting_count > waiting.length &&
              ` Showing ${waiting.length} of ${summary.awaiting_count}.`}
          </Typography>
          <IncidentMiniList incidents={waiting}
                            emptyText="Nothing new since you last looked." />
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>By status</Typography>
              <StatusCounts counts={byStatus} />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h2" gutterBottom>By priority</Typography>
              {Object.keys(byPriority).length === 0 ? (
                <Typography color="text.secondary">You have not reported anything yet.</Typography>
              ) : (
                <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
                  {Object.entries(byPriority).map(([priority, count]) => (
                    <Chip key={priority} label={`${label(priority)}: ${count}`} />
                  ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Stack>
  )
}
