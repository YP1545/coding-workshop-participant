import { useState } from 'react'
import { Alert, Box, Button, Card, CardContent, Link as MuiLink, Stack, TextField, Typography } from '@mui/material'
import { Link, useNavigate } from 'react-router-dom'
import * as authApi from '../api/authApi'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'

/**
 * Registration page.
 *
 * Part of: frontend / auth pages.
 *
 * Everyone registers as an employee — the backend ignores any role sent here,
 * and only a facility admin can promote someone afterwards.
 */
export default function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      await authApi.register(email, password, fullName)
      // Sign them straight in, so registering does not dump someone back on a
      // login form to type the same details again.
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center' }}>
      <Card sx={{ width: '100%', maxWidth: 420 }}>
        <CardContent>
          <Typography variant="h1" gutterBottom>
            Create an account
          </Typography>

          <Alert severity="info" sx={{ mb: 2 }}>
            Only @acme.inc email addresses can register.
          </Alert>

          <ErrorMessage error={error} />

          <Stack spacing={2} component="form" onSubmit={handleSubmit}>
            <TextField
              label="Full name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              fullWidth
            />
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              fullWidth
              placeholder="you@acme.inc"
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              fullWidth
              helperText="At least 8 characters"
              autoComplete="new-password"
            />
            <Button type="submit" variant="contained" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </Button>
          </Stack>

          <Typography variant="body2" sx={{ mt: 2 }}>
            Already have one?{' '}
            <MuiLink component={Link} to="/login">
              Sign in
            </MuiLink>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
