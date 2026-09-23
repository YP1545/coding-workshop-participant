/**
 * The fixed lists the backend accepts, and how to display them.
 *
 * Part of: frontend / shared.
 *
 * Why its own file: these values are enums in the database, so the frontend
 * must send exactly these strings. Writing them once here means a dropdown and
 * a filter bar can never drift apart, and a typo shows up in one place.
 */

export const STATUSES = ['open', 'in_progress', 'blocked', 'resolved', 'closed']

/** The normal path through the workflow. 'blocked' is a detour, not a step. */
export const WORKFLOW_STEPS = ['open', 'in_progress', 'resolved', 'closed']

export const PRIORITIES = ['low', 'medium', 'high', 'urgent']

// Categories deliberately live in the database, not here — see
// incidentsApi.listCategories(). They are the one list a facility admin can
// extend without a deploy, so hardcoding them would defeat the point.

export const AVAILABILITIES = ['available', 'busy', 'off']

export const ROLES = ['employee', 'facility_admin', 'engineer']

/** Turn a stored value like 'in_progress' into 'In progress' for display. */
export function label(value) {
  if (!value) return ''
  const spaced = value.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/**
 * The colour pair behind each status and priority pill.
 *
 * Why pairs rather than MUI's `color="error"` shorthand: a solid red chip on a
 * white table row shouts, and a row can carry two of them. A tinted background
 * with a dark version of the same hue for the text stays legible (every pair
 * below is above 4.5:1 on its own background) while letting the row read as a
 * row rather than a set of badges.
 */
export const STATUS_TONE = {
  open: { bg: '#F2F4F7', fg: '#344054' },
  in_progress: { bg: '#EFF8FF', fg: '#175CD3' },
  blocked: { bg: '#FEF3F2', fg: '#B42318' },
  resolved: { bg: '#ECFDF3', fg: '#027A48' },
  closed: { bg: '#F2F4F7', fg: '#667085' },
}

/** The same idea for priority. Urgent is the only one that uses red. */
export const PRIORITY_TONE = {
  low: { bg: '#ECFDF3', fg: '#027A48' },
  medium: { bg: '#FFFAEB', fg: '#B54708' },
  high: { bg: '#FFF4ED', fg: '#C4320A' },
  urgent: { bg: '#FEF3F2', fg: '#B42318' },
}

/** Fallback so an unknown value still renders as a readable grey pill. */
export const NEUTRAL_TONE = { bg: '#F2F4F7', fg: '#344054' }

/**
 * "12 min ago" for a recent timestamp, falling back to the date for old ones.
 *
 * A dashboard is read at a glance, and "2 hours ago" answers "is this still
 * happening?" faster than a formatted date does. Past about a week the
 * relative form stops helping, so the date comes back.
 */
export function timeAgo(value) {
  if (!value) return '\u2014'

  const then = new Date(value)
  const minutes = Math.round((Date.now() - then.getTime()) / 60000)

  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`

  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`

  const days = Math.round(hours / 24)
  if (days <= 7) return `${days} day${days === 1 ? '' : 's'} ago`

  return then.toLocaleDateString()
}

/** Format an ISO timestamp from the API for display, or '—' when absent. */
export function formatDate(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}
