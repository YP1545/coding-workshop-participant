import { useEffect, useState } from 'react'
import {
  Box, Card, CardContent, CircularProgress, Grid, InputAdornment, MenuItem,
  Pagination, Stack, TextField, Typography, Button,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import { Link, useSearchParams } from 'react-router-dom'
import * as incidentsApi from '../api/incidentsApi'
import * as facilitiesApi from '../api/facilitiesApi'
import * as engineersApi from '../api/engineersApi'
import { useAuth } from '../auth/useAuth'
import ErrorMessage from '../components/ErrorMessage'
import IncidentTable from '../components/IncidentTable'
import { PRIORITIES, STATUSES, label } from '../constants'

/**
 * The incident list: search, filters, and one page at a time.
 *
 * Part of: frontend / incidents.
 *
 * Searching and filtering are done by the API, not in the browser. The server
 * already limits what each person may see, so filtering there means rows the
 * caller is not entitled to are never fetched — and it is the only way paging
 * can be correct, since the page after the filter is not the filter after the
 * page.
 */

/** Incidents per page. Ten fits on a laptop screen without scrolling past it. */
const PAGE_SIZE = 10

export default function IncidentsPage() {
  const { isEngineer } = useAuth()

  const [incidents, setIncidents] = useState([])
  const [total, setTotal] = useState(0)
  const [buildings, setBuildings] = useState([])
  const [engineers, setEngineers] = useState([])
  const [categories, setCategories] = useState([])
  const [filters, setFilters] = useState({
    status: '', priority: '', category: '', building_id: '',
  })
  // The term actually being searched for lives in the URL, not in state. The
  // search bar sits in the app frame, so a second search changes the address
  // without remounting this page — reading it from there means the list always
  // matches the address, and a filtered view is a link you can send to someone.
  const [searchParams, setSearchParams] = useSearchParams()
  const search = searchParams.get('search') || ''

  // What is typed, as opposed to what has been searched for. They differ while
  // somebody is still typing: firing a request per keystroke would send one
  // query for every letter of "radiator".
  const [searchText, setSearchText] = useState(search)
  const [page, setPage] = useState(1)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  // Searching from the bar in the app frame changes the URL without remounting
  // this page, so the page number would survive the search: search from page 3
  // and you would land on page 3 of the new results, which is usually empty and
  // reads as "nothing found". Adjusting during render rather than in an effect
  // is React's documented way to reset state when an input changes — an effect
  // would render the wrong page once before correcting itself.
  const [lastSearch, setLastSearch] = useState(search)
  if (search !== lastSearch) {
    setLastSearch(search)
    setSearchText(search)
    setPage(1)
  }

  useEffect(() => {
    incidentsApi
      .listIncidents({
        ...filters,
        search,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      .then((result) => {
        setIncidents(result.items)
        setTotal(result.total)
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [filters, search, page])

  const pageCount = Math.ceil(total / PAGE_SIZE)

  // Buildings fill the filter dropdown; engineers turn an assignee id in the
  // table into a name. Both fail quietly: a missing lookup costs a dash in one
  // column, which is not a reason to fail the whole page.
  useEffect(() => {
    facilitiesApi.listBuildings().then(setBuildings).catch(() => setBuildings([]))
    engineersApi.listEngineers().then(setEngineers).catch(() => setEngineers([]))
    incidentsApi.listCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  // Id-to-name lookups, built once per render from the lists above.
  const buildingNames = Object.fromEntries(buildings.map((b) => [b.id, b.name]))
  const assigneeNames = Object.fromEntries(
    engineers.map((e) => [e.id, e.full_name || 'Engineer']),
  )

  /**
   * Change a filter and go back to the first page.
   *
   * Without the reset, narrowing the filters while on page 4 would leave
   * somebody looking at an empty page and wondering where their incidents went.
   */
  function updateFilter(name, value) {
    setFilters({ ...filters, [name]: value })
    setPage(1)
  }

  function runSearch(event) {
    event.preventDefault()
    const term = searchText.trim()
    // replace rather than push: typing three refinements should not mean three
    // presses of the back button to leave the page.
    setSearchParams(term ? { search: term } : {}, { replace: true })
    setPage(1)
  }

  function clearSearch() {
    setSearchText('')
    setSearchParams({}, { replace: true })
    setPage(1)
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" useFlexGap sx={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h1">Incidents</Typography>
          <Typography color="text.secondary">
            {isEngineer
              ? 'Assigned to you, plus open work you can pick up.'
              : 'Incidents you can see.'}
          </Typography>
        </Box>
        <Button variant="contained" component={Link} to="/incidents/new">
          Report an incident
        </Button>
      </Stack>

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Box component="form" onSubmit={runSearch}>
              <TextField
                fullWidth size="small" label="Search incidents"
                placeholder="Ticket number, or words from the title"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
                    ),
                  },
                }}
                helperText={search ? `Showing matches for "${search}"` : 'Search INC-0042, or any word. Press Enter.'}
              />
            </Box>

            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField select fullWidth size="small" label="Status" value={filters.status}
                           onChange={(event) => updateFilter('status', event.target.value)}>
                  <MenuItem value="">Any status</MenuItem>
                  {STATUSES.map((status) => (
                    <MenuItem key={status} value={status}>{label(status)}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField select fullWidth size="small" label="Priority" value={filters.priority}
                           onChange={(event) => updateFilter('priority', event.target.value)}>
                  <MenuItem value="">Any priority</MenuItem>
                  {PRIORITIES.map((priority) => (
                    <MenuItem key={priority} value={priority}>{label(priority)}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField select fullWidth size="small" label="Category" value={filters.category}
                           onChange={(event) => updateFilter('category', event.target.value)}>
                  <MenuItem value="">Any category</MenuItem>
                  {categories.map((category) => (
                    <MenuItem key={category.slug} value={category.slug}>{category.name}</MenuItem>
                  ))}
                </TextField>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <TextField select fullWidth size="small" label="Building" value={filters.building_id}
                           onChange={(event) => updateFilter('building_id', event.target.value)}>
                  <MenuItem value="">Any building</MenuItem>
                  {buildings.map((building) => (
                    <MenuItem key={building.id} value={building.id}>{building.name}</MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>

            {search && (
              <Box>
                <Button size="small" onClick={clearSearch}>Clear search</Button>
              </Box>
            )}
          </Stack>
        </CardContent>
      </Card>

      <ErrorMessage error={error} />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : incidents.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">
              {search
                ? `Nothing matches "${search}" with these filters.`
                : 'No incidents match these filters.'}
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary">
            {total} incident{total === 1 ? '' : 's'} found
            {pageCount > 1 && ` — page ${page} of ${pageCount}`}
          </Typography>

          <IncidentTable incidents={incidents} buildingNames={buildingNames}
                         assigneeNames={assigneeNames} />

          {pageCount > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 1 }}>
              <Pagination count={pageCount} page={page} color="primary"
                          onChange={(event, value) => setPage(value)} />
            </Box>
          )}
        </>
      )}
    </Stack>
  )
}
