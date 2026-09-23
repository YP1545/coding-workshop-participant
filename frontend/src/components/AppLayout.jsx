import { useState } from 'react'
import {
  Avatar, Box, Button, Container, Divider, Drawer, IconButton, InputAdornment,
  List, ListItemButton, ListItemIcon, ListItemText, Menu, MenuItem,
  TextField, Toolbar, Typography,
} from '@mui/material'
import ApartmentIcon from '@mui/icons-material/ApartmentOutlined'
import BadgeIcon from '@mui/icons-material/BadgeOutlined'
import BuildIcon from '@mui/icons-material/BuildOutlined'
import DomainIcon from '@mui/icons-material/DomainOutlined'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import GroupIcon from '@mui/icons-material/GroupOutlined'
import HomeIcon from '@mui/icons-material/HomeOutlined'
import InboxIcon from '@mui/icons-material/MoveToInboxOutlined'
import MenuIcon from '@mui/icons-material/Menu'
import PersonIcon from '@mui/icons-material/PersonOutlined'
import SearchIcon from '@mui/icons-material/Search'
import WarningIcon from '@mui/icons-material/WarningAmberOutlined'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useMediaQuery } from 'react-responsive'
import { useAuth } from '../auth/useAuth'
import { SIDEBAR, BORDER } from '../theme'

/**
 * The frame around every page: the navigation rail, the bar above the content,
 * and the routed page itself.
 *
 * Part of: frontend / layout.
 *
 * Why a rail rather than links across the top: an admin has seven destinations,
 * which is more than fits on one line at tablet width — the old bar had to
 * collapse into a menu, and a menu hides where you are. Down the side there is
 * room for every link plus its icon at any width, and the current page can stay
 * visibly marked.
 *
 * The links are built from the signed-in role, so nobody is offered a door that
 * will not open for them. That is a convenience, not the security boundary: the
 * API checks the same rules on every request.
 */

// Below this the rail would take too much of a narrow screen, so it becomes a
// drawer behind a button. Chosen from the width of the rail plus a readable
// content column, not from a device size.
const RAIL_MIN_WIDTH = 1024

/** Initials for the avatar: "Dana Okafor" becomes "DO". */
function initials(fullName) {
  if (!fullName) return '?'
  return fullName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

export default function AppLayout() {
  const { user, isAdmin, isEngineer, logout } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [userMenu, setUserMenu] = useState(null)
  const [searchText, setSearchText] = useState('')

  const isNarrow = useMediaQuery({ maxWidth: RAIL_MIN_WIDTH })

  // Built fresh each render so it always matches who is signed in.
  const navItems = []
  if (user) {
    navItems.push({ label: 'Dashboard', to: '/', icon: HomeIcon })
    navItems.push({ label: 'Incidents', to: '/incidents', icon: WarningIcon })
    if (isAdmin) {
      navItems.push({ label: 'Requests', to: '/assignment-requests', icon: InboxIcon })
      navItems.push({ label: 'Facilities', to: '/facilities', icon: ApartmentIcon })
      navItems.push({ label: 'People', to: '/people', icon: GroupIcon })
      navItems.push({ label: 'Engineers', to: '/engineers', icon: BuildIcon })
    }
    // Engineers manage their own requests, not the roster. Deciding who is an
    // engineer is a facility admin's job.
    if (isEngineer) {
      navItems.push({ label: 'My requests', to: '/my-requests', icon: BadgeIcon })
    }
    navItems.push({ label: 'Profile', to: '/profile', icon: PersonIcon })
  }

  function handleSignOut() {
    setUserMenu(null)
    logout()
    navigate('/login')
  }

  /** Send the top-bar search to the incidents page, which does the filtering. */
  function handleSearch(event) {
    event.preventDefault()
    const term = searchText.trim()
    navigate(term ? `/incidents?search=${encodeURIComponent(term)}` : '/incidents')
    setDrawerOpen(false)
  }

  const railContent = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: SIDEBAR.bg }}>
      <Toolbar sx={{ gap: 1.5, borderBottom: `1px solid ${SIDEBAR.border}` }}>
        <DomainIcon sx={{ color: SIDEBAR.activeBg }} />
        <Typography component={Link} to="/" noWrap
                    sx={{
                      color: SIDEBAR.textActive, textDecoration: 'none',
                      fontWeight: 700, fontSize: '1.05rem',
                      display: 'flex', alignItems: 'center', minHeight: 44, minWidth: 0,
                      overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>
          Incident Operations
        </Typography>
      </Toolbar>

      <List sx={{ p: 1.5, flexGrow: 1 }}>
        {navItems.map((item) => {
          const Icon = item.icon
          const active = pathname === item.to
          return (
            <ListItemButton
              key={item.to}
              component={Link}
              to={item.to}
              onClick={() => setDrawerOpen(false)}
              // aria-current tells a screen reader which page this is, which
              // the colour alone does not.
              aria-current={active ? 'page' : undefined}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: active ? SIDEBAR.textActive : SIDEBAR.text,
                bgcolor: active ? SIDEBAR.activeBg : 'transparent',
                '&:hover': { bgcolor: active ? SIDEBAR.activeBg : SIDEBAR.hoverBg },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: 40 }}>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary={item.label}
                            slotProps={{ primary: { fontWeight: active ? 600 : 500 } }} />
            </ListItemButton>
          )
        })}
      </List>

      <Box sx={{ p: 2.5, borderTop: `1px solid ${SIDEBAR.border}` }}>
        <Typography variant="caption" sx={{ color: SIDEBAR.text, display: 'block' }}>
          Safe buildings.
        </Typography>
        <Typography variant="caption" sx={{ color: SIDEBAR.text, display: 'block' }}>
          Stronger operations.
        </Typography>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {user && !isNarrow && (
        <Drawer
          variant="permanent"
          sx={{
            width: SIDEBAR.width,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: SIDEBAR.width, boxSizing: 'border-box', border: 'none',
            },
          }}
        >
          {railContent}
        </Drawer>
      )}

      {user && isNarrow && (
        <Drawer
          variant="temporary"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          sx={{ '& .MuiDrawer-paper': { width: SIDEBAR.width, border: 'none' } }}
        >
          {railContent}
        </Drawer>
      )}

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0 }}>
        <Box
          sx={{
            // Sticky so search and the account menu stay reachable while a long
            // incident list scrolls underneath.
            position: 'sticky', top: 0, zIndex: 1100,
            bgcolor: 'background.paper', borderBottom: `1px solid ${BORDER}`,
          }}
        >
          <Toolbar sx={{ gap: 1.5 }}>
            {user && isNarrow && (
              <IconButton edge="start" aria-label="Open navigation"
                          onClick={() => setDrawerOpen(true)}>
                <MenuIcon />
              </IconButton>
            )}

            {user ? (
              <>
                <Box component="form" onSubmit={handleSearch}
                     sx={{ flexGrow: 1, maxWidth: 560, minWidth: 0 }}>
                  <TextField
                    size="small"
                    fullWidth
                    value={searchText}
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="Search incidents or INC-0042…"
                    slotProps={{
                      htmlInput: { 'aria-label': 'Search incidents' },
                      input: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                          </InputAdornment>
                        ),
                        sx: { borderRadius: 999 },
                      },
                    }}
                  />
                </Box>

                <Box sx={{ flexGrow: 1 }} />

                <Button
                  onClick={(event) => setUserMenu(event.currentTarget)}
                  endIcon={<ExpandMoreIcon />}
                  sx={{ color: 'text.primary', gap: 0.5 }}
                >
                  <Avatar sx={{ width: 32, height: 32, mr: 1, fontSize: '0.8rem',
                                bgcolor: 'primary.main' }}>
                    {initials(user.full_name)}
                  </Avatar>
                  {/* The name is the first thing to drop on a narrow screen —
                      the avatar already says who is signed in. */}
                  <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>
                    {user.full_name}
                  </Box>
                </Button>
              </>
            ) : (
              <>
                <Typography component={Link} to="/"
                            sx={{ fontWeight: 700, color: 'text.primary',
                                  textDecoration: 'none', display: 'flex',
                                  alignItems: 'center', minHeight: 44, flexGrow: 1 }}>
                  Incident Operations
                </Typography>
                <Button component={Link} to="/login" variant="contained">
                  Sign in
                </Button>
              </>
            )}
          </Toolbar>
        </Box>

        <Menu anchorEl={userMenu} open={Boolean(userMenu)} onClose={() => setUserMenu(null)}>
          <MenuItem component={Link} to="/profile" onClick={() => setUserMenu(null)}>
            Profile
          </MenuItem>
          <Divider />
          <MenuItem onClick={handleSignOut}>Sign out</MenuItem>
        </Menu>

        <Container maxWidth="xl" sx={{ py: 4 }}>
          <Outlet />
        </Container>
      </Box>
    </Box>
  )
}
