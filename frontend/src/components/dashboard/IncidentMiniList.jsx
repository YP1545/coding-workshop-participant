import { Box, List, ListItem, ListItemText, Stack, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import StatusChip from '../StatusChip'
import { formatDate, label } from '../../constants'

/**
 * A short list of incidents, each linking to its own page.
 *
 * Part of: frontend / dashboard.
 *
 * Used for "waiting on you" and "assigned to you". Deliberately short: a
 * dashboard that lists everything is just the incidents page with worse
 * filtering.
 */
export default function IncidentMiniList({ incidents, emptyText }) {
  if (!incidents || incidents.length === 0) {
    return <Typography color="text.secondary">{emptyText}</Typography>
  }

  return (
    <List dense>
      {incidents.map((incident) => (
        <ListItem key={incident.id} disableGutters component={Link}
                  to={`/incidents/${incident.id}`}
                  sx={{ color: 'inherit', textDecoration: 'none' }}>
          <ListItemText
            primary={
              <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <Box>{incident.title}</Box>
                <StatusChip status={incident.status} />
                <StatusChip priority={incident.priority} />
              </Stack>
            }
            secondary={`${label(incident.category)} · reported ${formatDate(incident.created_at)}`}
          />
        </ListItem>
      ))}
    </List>
  )
}
