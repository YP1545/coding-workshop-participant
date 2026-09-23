import { Box, Stack, Typography } from '@mui/material'
import StatusChip from '../StatusChip'
import { STATUSES } from '../../constants'

/**
 * A row per status with its count.
 *
 * Part of: frontend / dashboard.
 *
 * Shared by all three dashboards. Every status is listed even when it is zero,
 * so the shape of the list does not jump about as incidents move — and a zero
 * is information too.
 */
export default function StatusCounts({ counts }) {
  return (
    <Stack spacing={1}>
      {STATUSES.map((status) => (
        <Stack key={status} direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Box sx={{ minWidth: 110 }}>
            <StatusChip status={status} />
          </Box>
          <Typography>{counts[status] || 0}</Typography>
        </Stack>
      ))}
    </Stack>
  )
}
