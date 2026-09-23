import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'
import AssignmentRequestsPage from './pages/AssignmentRequestsPage'
import DashboardPage from './pages/DashboardPage'
import EngineersPage from './pages/EngineersPage'
import FacilitiesPage from './pages/FacilitiesPage'
import IncidentDetailPage from './pages/IncidentDetailPage'
import IncidentsPage from './pages/IncidentsPage'
import LoginPage from './pages/LoginPage'
import MyRequestsPage from './pages/MyRequestsPage'
import PeoplePage from './pages/PeoplePage'
import NewIncidentPage from './pages/NewIncidentPage'
import ProfilePage from './pages/ProfilePage'
import RegisterPage from './pages/RegisterPage'

/**
 * Every page in the app, and who is allowed to open it.
 *
 * Part of: frontend / routing.
 *
 * ProtectedRoute is a convenience for the person using the app, not a security
 * boundary — the same rules are enforced by the API on every request. Reading
 * this file should tell you the shape of the whole product.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />

        <Route index element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="incidents" element={<ProtectedRoute><IncidentsPage /></ProtectedRoute>} />
        <Route path="incidents/new" element={<ProtectedRoute><NewIncidentPage /></ProtectedRoute>} />
        <Route path="incidents/:incidentId" element={<ProtectedRoute><IncidentDetailPage /></ProtectedRoute>} />
        <Route path="profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />

        <Route path="my-requests" element={
          <ProtectedRoute roles={['engineer']}><MyRequestsPage /></ProtectedRoute>} />

        <Route path="assignment-requests" element={
          <ProtectedRoute roles={['facility_admin']}><AssignmentRequestsPage /></ProtectedRoute>} />
        <Route path="facilities" element={
          <ProtectedRoute roles={['facility_admin']}><FacilitiesPage /></ProtectedRoute>} />
        <Route path="people" element={
          <ProtectedRoute roles={['facility_admin']}><PeoplePage /></ProtectedRoute>} />
        <Route path="engineers" element={
          <ProtectedRoute roles={['facility_admin']}><EngineersPage /></ProtectedRoute>} />

        <Route path="*" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      </Route>
    </Routes>
  )
}
