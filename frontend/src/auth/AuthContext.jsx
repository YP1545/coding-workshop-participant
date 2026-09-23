import { useEffect, useState } from 'react'
import * as authApi from '../api/authApi'
import { AuthContext } from './authContext'
import { setAuthToken } from '../api/client'

/**
 * Who is signed in, for the whole app.
 *
 * Part of: frontend / auth.
 *
 * Why its own file: the token and the current user are needed by almost every
 * page — the nav bar, the route guards, and every screen that shows or hides a
 * button by role. A React context means they are read from one place instead
 * of being passed down through every component in between.
 *
 * The token is kept in localStorage so a page refresh does not sign you out.
 * That is a deliberate trade-off: it survives refresh, but any script running
 * on the page could read it. For this app, with a 24 hour token and no
 * payments, that is the normal choice.
 */

const STORAGE_KEY = 'acme.token'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Only "loading" if there is actually a stored token to check. Working that
  // out here, rather than setting it inside the effect, avoids an extra render
  // and means someone with no token never sees a spinner before the login page.
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem(STORAGE_KEY)))

  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_KEY)

    if (!storedToken) {
      return
    }

    setAuthToken(storedToken)

    // Ask the backend who this token belongs to. If it has expired or the
    // account is gone, the call fails and we clear it rather than leaving the
    // app in a half-signed-in state.
    authApi
      .getCurrentUser()
      .then((currentUser) => setUser(currentUser))
      .catch(() => {
        localStorage.removeItem(STORAGE_KEY)
        setAuthToken(null)
      })
      .finally(() => setLoading(false))
  }, [])

  /** Sign in and remember the token. Throws if the credentials are wrong. */
  async function login(email, password) {
    const session = await authApi.login(email, password)
    localStorage.setItem(STORAGE_KEY, session.access_token)
    setAuthToken(session.access_token)
    setUser(session.user)
    return session.user
  }

  /** Sign out. There is no server call: the token simply stops being sent. */
  function logout() {
    localStorage.removeItem(STORAGE_KEY)
    setAuthToken(null)
    setUser(null)
  }

  const value = {
    user,
    role: user ? user.role : null,
    isAdmin: user ? user.role === 'facility_admin' : false,
    isEngineer: user ? user.role === 'engineer' : false,
    loading,
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
