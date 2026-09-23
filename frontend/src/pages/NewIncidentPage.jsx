import { useEffect, useState } from 'react'
import {
  Box, Button, Card, CardContent, Grid, MenuItem, Stack, TextField, Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import * as facilitiesApi from '../api/facilitiesApi'
import * as incidentsApi from '../api/incidentsApi'
import ErrorMessage from '../components/ErrorMessage'
import { PRIORITIES, label } from '../constants'

/**
 * The form for reporting a new incident.
 *
 * Part of: frontend / incidents.
 *
 * Building, floor and seat cascade: picking a building loads its floors, and
 * picking a floor loads its seats. All three are optional, because a network
 * fault might only have a seat and a lift fault only a building.
 */
export default function NewIncidentPage() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    title: '', description: '', category: 'other', priority: 'medium',
    building_id: '', floor_id: '', seat_id: '',
  })
  const [buildings, setBuildings] = useState([])
  const [categories, setCategories] = useState([])
  const [floors, setFloors] = useState([])
  const [seats, setSeats] = useState([])
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    facilitiesApi.listBuildings().then(setBuildings).catch((err) => setError(err))
    // The category list comes from the database, so one added there shows up
    // here without a frontend change.
    incidentsApi.listCategories().then(setCategories).catch((err) => setError(err))
  }, [])

  // Load the floors of the chosen building. Clearing the lists happens in
  // update() below rather than here: emptying them is a consequence of the
  // person changing the dropdown, not of the data arriving.
  useEffect(() => {
    if (!form.building_id) return
    facilitiesApi.listFloors(form.building_id).then(setFloors).catch(() => setFloors([]))
  }, [form.building_id])

  useEffect(() => {
    if (!form.floor_id) return
    facilitiesApi.listSeats(form.floor_id).then(setSeats).catch(() => setSeats([]))
  }, [form.floor_id])

  function update(name, value) {
    // Changing a building clears the floor and seat under it, so the form can
    // never end up holding a seat that belongs to a different building.
    if (name === 'building_id') {
      setForm({ ...form, building_id: value, floor_id: '', seat_id: '' })
      setFloors([])
      setSeats([])
    } else if (name === 'floor_id') {
      setForm({ ...form, floor_id: value, seat_id: '' })
      setSeats([])
    } else {
      setForm({ ...form, [name]: value })
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)

    // Empty strings would be sent as invalid UUIDs, so the optional location
    // fields are only included when something was actually picked.
    const payload = {
      title: form.title,
      description: form.description,
      category: form.category,
      priority: form.priority,
    }
    if (form.building_id) payload.building_id = form.building_id
    if (form.floor_id) payload.floor_id = form.floor_id
    if (form.seat_id) payload.seat_id = form.seat_id

    try {
      const incident = await incidentsApi.createIncident(payload)
      navigate(`/incidents/${incident.id}`)
    } catch (err) {
      setError(err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box sx={{ maxWidth: 720, mx: 'auto' }}>
      <Typography variant="h1" gutterBottom>Report an incident</Typography>

      <Card>
        <CardContent>
          <ErrorMessage error={error} />

          <Stack spacing={2} component="form" onSubmit={handleSubmit}>
            <TextField label="What is wrong?" value={form.title} required fullWidth
                       onChange={(event) => update('title', event.target.value)}
                       placeholder="Meeting room AC blowing warm air" />

            <TextField label="Description" value={form.description} required fullWidth
                       multiline rows={4}
                       onChange={(event) => update('description', event.target.value)}
                       placeholder="Any detail that would help whoever picks this up." />

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField select label="Category" value={form.category} fullWidth
                           onChange={(event) => update('category', event.target.value)}>
                  {categories.map((category) => (
                    <MenuItem key={category.slug} value={category.slug}>{category.name}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField select label="Priority" value={form.priority} fullWidth
                           onChange={(event) => update('priority', event.target.value)}
                           helperText="A facility admin may adjust this.">
                  {PRIORITIES.map((priority) => (
                    <MenuItem key={priority} value={priority}>{label(priority)}</MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>

            <Typography variant="h2" sx={{ pt: 1 }}>Where is it? (optional)</Typography>

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField select label="Building" value={form.building_id} fullWidth
                           onChange={(event) => update('building_id', event.target.value)}>
                  <MenuItem value="">Not sure</MenuItem>
                  {buildings.map((building) => (
                    <MenuItem key={building.id} value={building.id}>{building.name}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField select label="Floor" value={form.floor_id} fullWidth
                           disabled={!form.building_id}
                           onChange={(event) => update('floor_id', event.target.value)}>
                  <MenuItem value="">Not sure</MenuItem>
                  {floors.map((floor) => (
                    <MenuItem key={floor.id} value={floor.id}>{floor.name}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField select label="Seat" value={form.seat_id} fullWidth
                           disabled={!form.floor_id}
                           onChange={(event) => update('seat_id', event.target.value)}>
                  <MenuItem value="">Not sure</MenuItem>
                  {seats.map((seat) => (
                    <MenuItem key={seat.id} value={seat.id}>{seat.label}</MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>

            <Stack direction="row" spacing={2}>
              <Button type="submit" variant="contained" disabled={submitting}>
                {submitting ? 'Reporting…' : 'Report incident'}
              </Button>
              <Button onClick={() => navigate('/incidents')}>Cancel</Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}
