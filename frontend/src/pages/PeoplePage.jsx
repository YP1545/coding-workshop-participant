import { useEffect, useState } from 'react'
import {
  Alert, Box, Card, CardContent, MenuItem, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import { useMediaQuery } from 'react-responsive'
import * as authApi from '../api/authApi'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'
import { ROLES, label } from '../constants'

/**
 * Everyone with an account, and what they are allowed to do.
 *
 * Part of: frontend / people (admin).
 *
 * The role dropdown is the whole control. Choosing "Engineer" also creates
 * their engineer profile, so they appear on the rota and can be assigned work
 * straight away; choosing anything else takes them off it again. The profile
 * itself is kept either way, so the record of what they worked on survives —
 * see the role endpoint in users-service for why that matters.
 */
export default function PeoplePage() {
  const isMobile = useMediaQuery({ maxWidth: 700 })
  const { user } = useAuth()

  const [people, setPeople] = useState([])
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)

  function load() {
    authApi.listUsers().then(setPeople).catch((err) => setError(err))
  }

  useEffect(load, [])

  async function run(action, successMessage) {
    setError(null)
    setMessage(null)
    try {
      await action()
      setMessage(successMessage)
      load()
    } catch (err) {
      setError(err)
    }
  }

  function RolePicker({ person }) {
    // An admin cannot change their own role — the server refuses it too, so
    // that the last admin cannot lock everyone out of facility management.
    const isSelf = person.id === user.id

    return (
      <TextField select size="small" value={person.role} sx={{ minWidth: 150 }} disabled={isSelf}
                 helperText={isSelf ? 'This is you' : ''}
                 onChange={(event) =>
                   run(() => authApi.updateUserRole(person.id, event.target.value),
                       `${person.full_name} is now ${label(event.target.value)}.`)}>
        {ROLES.map((role) => (
          <MenuItem key={role} value={role}>{label(role)}</MenuItem>
        ))}
      </TextField>
    )
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">People</Typography>
        <Typography color="text.secondary">
          Everyone who has registered, and what they can do.
        </Typography>
      </Box>

      <Alert severity="info">
        Anyone with an @acme.inc address can register themselves — they start as an employee.
        Setting someone&apos;s role to <strong>Engineer</strong> puts them on the rota so
        incidents can be assigned to them; changing it back takes them off it.
      </Alert>

      <ErrorMessage error={error} />
      {message && <Alert severity="success">{message}</Alert>}

      {isMobile ? (
        <Stack spacing={2}>
          {people.map((person) => (
            <Card key={person.id}>
              <CardContent>
                <Typography variant="h6">{person.full_name}</Typography>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {person.email}
                </Typography>
                <Stack spacing={1} sx={{ mt: 1 }}>
                  <RolePicker person={person} />
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
                <TableCell>Role</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {people.map((person) => (
                <TableRow key={person.id}>
                  <TableCell>{person.full_name}</TableCell>
                  <TableCell>{person.email}</TableCell>
                  <TableCell><RolePicker person={person} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Stack>
  )
}
