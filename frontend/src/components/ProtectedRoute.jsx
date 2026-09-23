import { Box, CircularProgress } from '@mui/material'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

/**
 * Wraps a page so only the right people can open it.
 *
 * Part of: frontend / auth.
 *
 * This is a convenience, not the security boundary. Hiding a page in the
 * browser stops an honest person taking a wrong turn; it stops nobody from
 * calling the API directly. Every rule here is enforced again on the server,
 * which is what actually protects the data.
 *
 * @param {string[]} [roles] Roles allowed to see this page. Any signed-in user
 *   may see it when this is left out.
 */
export default function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth()

  // Wait for the stored token to be checked before deciding anything, or a
  // refresh would bounce a signed-in user to the login page.
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />
  }

  return children
}
