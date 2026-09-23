import { useState } from 'react'
import { Box, Button, Card, CardContent, Link as MuiLink, Stack, TextField, Typography } from '@mui/material'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'

/**
 * Sign-in page.
 *
 * Part of: frontend / auth pages.
 */
export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  // Disables the button while the request is in flight, so an impatient
  // double-click cannot send two login attempts.
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
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
            Sign in
          </Typography>
          <Typography color="text.secondary" gutterBottom>
            Use your @acme.inc account.
          </Typography>

          <ErrorMessage error={error} />

          <Stack spacing={2} sx={{ mt: 2 }} component="form" onSubmit={handleSubmit}>
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              fullWidth
              autoComplete="email"
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              fullWidth
              autoComplete="current-password"
            />
            <Button type="submit" variant="contained" disabled={submitting}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </Stack>

          <Typography variant="body2" sx={{ mt: 2 }}>
            No account yet?{' '}
            <MuiLink component={Link} to="/register">
              Register
            </MuiLink>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
