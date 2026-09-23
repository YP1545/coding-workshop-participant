import { useEffect, useState } from 'react'
import {
  Accordion, AccordionDetails, AccordionSummary, Box, Button, Card, CardContent,
  Chip, IconButton, Stack, TextField, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import DeleteIcon from '@mui/icons-material/Delete'
import * as facilitiesApi from '../api/facilitiesApi'
import ErrorMessage from '../components/ErrorMessage'

/**
 * Managing buildings, floors and seats.
 *
 * Part of: frontend / facilities (admin).
 *
 * Shown as a tree of accordions: a building opens to its floors, a floor opens
 * to its seats. Floors and seats are only fetched when a building is opened,
 * so a site with fifty buildings does not load every seat up front.
 */
export default function FacilitiesPage() {
  const [buildings, setBuildings] = useState([])
  const [floorsByBuilding, setFloorsByBuilding] = useState({})
  const [seatsByFloor, setSeatsByFloor] = useState({})
  const [newBuilding, setNewBuilding] = useState({ name: '', address: '' })
  const [error, setError] = useState(null)

  function loadBuildings() {
    facilitiesApi.listBuildings().then(setBuildings).catch((err) => setError(err))
  }

  useEffect(loadBuildings, [])

  function loadFloors(buildingId) {
    facilitiesApi
      .listFloors(buildingId)
      .then((floors) => setFloorsByBuilding((current) => ({ ...current, [buildingId]: floors })))
      .catch((err) => setError(err))
  }

  function loadSeats(floorId) {
    facilitiesApi
      .listSeats(floorId)
      .then((seats) => setSeatsByFloor((current) => ({ ...current, [floorId]: seats })))
      .catch((err) => setError(err))
  }

  /** Run a change, then refresh whatever it affected. */
  async function run(action, afterwards) {
    setError(null)
    try {
      await action()
      afterwards()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h1">Facilities</Typography>
        <Typography color="text.secondary">
          Buildings, the floors in them, and the seats on those floors.
        </Typography>
      </Box>

      <ErrorMessage error={error} />

      <Card>
        <CardContent>
          <Typography variant="h2" gutterBottom>Add a building</Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField size="small" label="Name" value={newBuilding.name} fullWidth
                       onChange={(event) => setNewBuilding({ ...newBuilding, name: event.target.value })} />
            <TextField size="small" label="Address (optional)" value={newBuilding.address} fullWidth
                       onChange={(event) => setNewBuilding({ ...newBuilding, address: event.target.value })} />
            <Button variant="contained" disabled={!newBuilding.name}
                    onClick={() => run(
                      () => facilitiesApi.createBuilding(newBuilding.name, newBuilding.address || null),
                      () => { setNewBuilding({ name: '', address: '' }); loadBuildings() },
                    )}>
              Add
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {buildings.map((building) => (
        <Accordion key={building.id} onChange={(event, expanded) => expanded && loadFloors(building.id)}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', width: '100%' }}>
              <Typography sx={{ flexGrow: 1 }}>{building.name}</Typography>
              <Typography variant="body2" color="text.secondary">{building.address}</Typography>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            <BuildingDetails
              building={building}
              floors={floorsByBuilding[building.id] || []}
              seatsByFloor={seatsByFloor}
              onLoadSeats={loadSeats}
              onChanged={() => loadFloors(building.id)}
              onBuildingDeleted={loadBuildings}
              run={run}
            />
          </AccordionDetails>
        </Accordion>
      ))}
    </Stack>
  )
}

/**
 * The floors and seats inside one building, plus the forms to change them.
 *
 * Split out of the page above so the page stays about the list, and this stays
 * about one building's contents.
 */
function BuildingDetails({ building, floors, seatsByFloor, onLoadSeats, onChanged, onBuildingDeleted, run }) {
  const [floorName, setFloorName] = useState('')
  const [seatLabels, setSeatLabels] = useState({})

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2}>
        <TextField size="small" label="New floor" value={floorName} fullWidth
                   onChange={(event) => setFloorName(event.target.value)} />
        <Button variant="outlined" disabled={!floorName}
                onClick={() => run(
                  () => facilitiesApi.createFloor(building.id, floorName),
                  () => { setFloorName(''); onChanged() },
                )}>
          Add floor
        </Button>
      </Stack>

      {floors.length === 0 && (
        <Typography variant="body2" color="text.secondary">No floors yet.</Typography>
      )}

      {floors.map((floor) => (
        <Card key={floor.id} variant="outlined">
          <CardContent>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
              <Typography sx={{ flexGrow: 1 }}>{floor.name}</Typography>
              <Button size="small" onClick={() => onLoadSeats(floor.id)}>Show seats</Button>
              <IconButton size="small" color="error"
                          onClick={() => run(() => facilitiesApi.deleteFloor(floor.id), onChanged)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>

            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mb: 1 }}>
              {(seatsByFloor[floor.id] || []).map((seat) => (
                <Chip key={seat.id} label={seat.label} size="small"
                      onDelete={() => run(() => facilitiesApi.deleteSeat(seat.id), () => onLoadSeats(floor.id))} />
              ))}
            </Stack>

            <Stack direction="row" spacing={1}>
              <TextField size="small" label="New seat" value={seatLabels[floor.id] || ''}
                         onChange={(event) => setSeatLabels({ ...seatLabels, [floor.id]: event.target.value })} />
              <Button size="small" disabled={!seatLabels[floor.id]}
                      onClick={() => run(
                        () => facilitiesApi.createSeat(floor.id, seatLabels[floor.id]),
                        () => { setSeatLabels({ ...seatLabels, [floor.id]: '' }); onLoadSeats(floor.id) },
                      )}>
                Add seat
              </Button>
            </Stack>
          </CardContent>
        </Card>
      ))}

      <Box>
        <Button size="small" color="error"
                onClick={() => run(() => facilitiesApi.deleteBuilding(building.id), onBuildingDeleted)}>
          Delete this building
        </Button>
        <Typography variant="caption" color="text.secondary" display="block">
          Only possible once its floors are gone.
        </Typography>
      </Box>
    </Stack>
  )
}
