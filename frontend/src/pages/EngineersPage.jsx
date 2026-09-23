import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, MenuItem, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import * as authApi from '../api/authApi'
import * as engineersApi from '../api/engineersApi'
import ErrorMessage from '../components/ErrorMessage'
import { AVAILABILITIES, label } from '../constants'

/**
 * The engineer roster.
 *
 * Part of: frontend / engineers (admin).
 *
 * Adding someone to the rota happens on the People page, not here: promoting an
 * account that already exists gives them a working login, where creating one
 * from an email address alone does not. This page manages who is already on it
 * — their specialty, whether they are free, and removing them.
 *
 * On a phone the table becomes a list of cards. A five-column table on a 375px
 * screen is unreadable, and this is one of the few places where reflowing is
 * not enough — which is why react-responsive is used here rather than a
 * breakpoint alone.
 *
 * "Remove from rota" changes their role back to employee rather than deleting
 * the engineer profile. Deleting it would blank the assignee on every incident
 * they ever worked, because incidents point at the profile with ON DELETE SET
 * NULL — so the record of who fixed what would go with them.
 */
export default function EngineersPage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })

  const [engineers, setEngineers] = useState([])
  // Used only by the disabled "Add an engineer" form below.
  // const [form, setForm] = useState({ email: '', full_name: '', specialty: '' })
  const [error, setError] = useState(null)

  function load() {
    engineersApi.listEngineers().then(setEngineers).catch((err) => setError(err))
  }

  useEffect(load, [])

  async function run(action) {
    setError(null)
    try {
      await action()
      load()
    } catch (err) {
      setError(err)
    }
  }

  function AvailabilityPicker({ engineer }) {
    return (
      <TextField select size="small" value={engineer.availability} sx={{ minWidth: 130 }}
                 onChange={(event) =>
                   run(() => engineersApi.updateEngineer(engineer.id, { availability: event.target.value }))}>
        {AVAILABILITIES.map((option) => (
          <MenuItem key={option} value={option}>{label(option)}</MenuItem>
        ))}
      </TextField>
    )
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">Engineers</Typography>
        <Typography color="text.secondary">
          Who is on the rota, what they cover, and whether they are free.
        </Typography>
      </Box>

      <ErrorMessage error={error} />

      {/*
        DISABLED for now — this form provisions a brand new account from an
        email address, and that account has no password, so the person cannot
        sign in. Until there is an invite or set-password flow, the working
        route onto the rota is People -> "Make engineer", which promotes
        somebody who already registered and chose their own password.

        The backend endpoint is untouched: "Make engineer" posts to the same
        POST /engineers with {user_id} instead of {email, full_name}.

        To bring it back: delete this comment wrapper, and uncomment the form
        state and the createEngineerAccount import above.

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Add an engineer</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Creates the account too. They will need a password set before they can sign in.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField size="small" label="Email" fullWidth value={form.email}
                       placeholder="name@acme.inc"
                       onChange={(event) => setForm({ ...form, email: event.target.value })} />
            <TextField size="small" label="Full name" fullWidth value={form.full_name}
                       onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
            <TextField size="small" label="Specialty" fullWidth value={form.specialty}
                       onChange={(event) => setForm({ ...form, specialty: event.target.value })} />
            <Button variant="contained" disabled={!form.email || !form.full_name}
                    onClick={() => run(async () => {
                      await engineersApi.createEngineerAccount(form.email, form.full_name, form.specialty || null)
                      setForm({ email: '', full_name: '', specialty: '' })
                    })}>
              Add
            </Button>
          </Stack>
        </CardContent>
      </Card>
      */}

      {isMobile ? (
        <Stack spacing={2}>
          {engineers.map((engineer) => (
            <Card key={engineer.id}>
              <CardContent>
                <Typography variant="h6">{engineer.full_name}</Typography>
                <Typography variant="body2" color="text.secondary">{engineer.email}</Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>{engineer.specialty || 'No specialty set'}</Typography>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                  <AvailabilityPicker engineer={engineer} />
                  <Button size="small" color="error"
                          onClick={() => run(() =>
                            authApi.updateUserRole(engineer.user_id, 'employee'))}>
                    Remove
                  </Button>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      ) : (
        <Card>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Specialty</TableCell>
                <TableCell>Availability</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {engineers.map((engineer) => (
                <TableRow key={engineer.id}>
                  <TableCell>{engineer.full_name}</TableCell>
                  <TableCell>{engineer.email}</TableCell>
                  <TableCell>{engineer.specialty || '—'}</TableCell>
                  <TableCell><AvailabilityPicker engineer={engineer} /></TableCell>
                  <TableCell align="right">
                    <Button size="small" color="error"
                            onClick={() => run(() =>
                              authApi.updateUserRole(engineer.user_id, 'employee'))}>
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Stack>
  )
}
