import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, MenuItem, Stack, TextField, Typography,
} from '@mui/material'
import * as engineersApi from '../api/engineersApi'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'
import { AVAILABILITIES, label } from '../constants'

/**
 * Your own account, and for engineers, your availability.
 *
 * Part of: frontend / profile.
 *
 * An engineer can change their availability but not their specialty — what
 * someone is qualified for is a management decision. The server enforces that;
 * the field is simply not offered here.
 */
export default function ProfilePage() {
  const { user, isEngineer, logout } = useAuth()

  const [profile, setProfile] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isEngineer) return
    engineersApi
      .listEngineers()
      .then((engineers) => setProfile(engineers.find((engineer) => engineer.user_id === user.id) || null))
      .catch((err) => setError(err))
  }, [isEngineer, user.id])

  async function setAvailability(availability) {
    setError(null)
    try {
      const updated = await engineersApi.updateEngineer(profile.id, { availability })
      setProfile(updated)
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Box sx={{ maxWidth: 560 }}>
      <Typography variant="h1" gutterBottom>Profile</Typography>

      <ErrorMessage error={error} />

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack spacing={1}>
            <Typography><strong>Name:</strong> {user.full_name}</Typography>
            <Typography><strong>Email:</strong> {user.email}</Typography>
            <Typography><strong>Role:</strong> {label(user.role)}</Typography>
          </Stack>
        </CardContent>
      </Card>

      {isEngineer && profile && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h2" gutterBottom>Availability</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Admins use this when deciding who to assign work to.
            </Typography>
            <TextField select size="small" value={profile.availability} sx={{ minWidth: 180 }}
                       onChange={(event) => setAvailability(event.target.value)}>
              {AVAILABILITIES.map((option) => (
                <MenuItem key={option} value={option}>{label(option)}</MenuItem>
              ))}
            </TextField>
            {profile.specialty && (
              <Typography variant="body2" sx={{ mt: 2 }}>
                <strong>Specialty:</strong> {profile.specialty} (set by an admin)
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      <Button variant="outlined" onClick={logout}>Sign out</Button>
    </Box>
  )
}
