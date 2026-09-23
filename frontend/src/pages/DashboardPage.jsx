import { useEffect, useState } from 'react'
import { Box, CircularProgress } from '@mui/material'
import * as incidentsApi from '../api/incidentsApi'
import { useAuth } from '../auth/useAuth'
import AdminDashboard from '../components/dashboard/AdminDashboard'
import EmployeeDashboard from '../components/dashboard/EmployeeDashboard'
import EngineerDashboard from '../components/dashboard/EngineerDashboard'
import ErrorMessage from '../components/ErrorMessage'

/**
 * The dashboard, which is really three dashboards.
 *
 * Part of: frontend / dashboard.
 *
 * This page only fetches and picks. The server decides what each role is
 * allowed to know and sends a different shape per persona, so the right
 * component is chosen from the `role` in the response rather than from the
 * signed-in user — that way the layout can never show a heading for figures
 * the response does not actually contain.
 */
export default function DashboardPage() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    incidentsApi
      .getDashboardSummary()
      .then((data) => setSummary(data))
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) return <ErrorMessage error={error} />
  if (!summary) return null

  if (summary.role === 'facility_admin') return <AdminDashboard summary={summary} />
  if (summary.role === 'engineer') return <EngineerDashboard summary={summary} user={user} />
  return <EmployeeDashboard summary={summary} user={user} />
}
