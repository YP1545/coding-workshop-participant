import { Alert } from '@mui/material'

/**
 * Shows an error from the API.
 *
 * Part of: frontend / shared components.
 *
 * Why its own file: every page that calls the API needs to show what went
 * wrong, and they should all look the same. The backend always sends errors as
 * {"detail": "..."}, and the api client turns that into error.detail, so this
 * prints the message the server actually gave rather than a generic one.
 */
export default function ErrorMessage({ error }) {
  if (!error) return null

  return (
    <Alert severity="error" sx={{ mb: 2 }}>
      {error.detail || error.message || 'Something went wrong'}
    </Alert>
  )
}
