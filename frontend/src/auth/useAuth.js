import { useContext } from 'react'
import { AuthContext } from './authContext'

/**
 * Read the signed-in user from anywhere in the app.
 *
 * Part of: frontend / auth.
 *
 * In its own file because AuthContext.jsx exports a component, and a file that
 * exports both a component and a plain function breaks Vite's fast refresh —
 * editing it would reload the whole page instead of just that component.
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return context
}
