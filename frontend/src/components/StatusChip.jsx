import { Box } from '@mui/material'
import { NEUTRAL_TONE, PRIORITY_TONE, STATUS_TONE, label } from '../constants'

/**
 * A soft pill showing a status or a priority.
 *
 * Part of: frontend / shared components.
 *
 * The colours come from constants.js so "urgent" is the same red on the
 * dashboard, in the list and on the detail page. Getting that wrong is a small
 * thing that makes an app feel unfinished.
 *
 * Why a Box rather than MUI's Chip: a Chip is built to be interactive — it
 * carries a minimum height, a ripple and a focus ring it never uses here. This
 * is a label, and a table row often holds two of them, so it stays small.
 *
 * @param {string} [status] One of STATUSES. Pass this or priority, not both.
 * @param {string} [priority] One of PRIORITIES.
 */
export default function StatusChip({ status, priority }) {
  const value = status || priority
  if (!value) return null

  const tone = (status ? STATUS_TONE[status] : PRIORITY_TONE[priority]) || NEUTRAL_TONE

  return (
    <Box
      component="span"
      sx={{
        display: 'inline-block',
        px: 1.25,
        py: 0.25,
        borderRadius: 999,
        bgcolor: tone.bg,
        color: tone.fg,
        fontSize: '0.75rem',
        fontWeight: 600,
        lineHeight: 1.7,
        whiteSpace: 'nowrap',
      }}
    >
      {label(value)}
    </Box>
  )
}
