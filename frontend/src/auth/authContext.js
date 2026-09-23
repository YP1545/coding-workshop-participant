import { createContext } from 'react'

/**
 * The context object holding the signed-in user.
 *
 * Part of: frontend / auth.
 *
 * In its own file, separate from the provider component and the useAuth hook,
 * because Vite's fast refresh only works when a file exports components alone.
 * Splitting them means editing a page reloads that component instead of the
 * whole app — a small thing that matters a lot while building.
 */
export const AuthContext = createContext(null)
