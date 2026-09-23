import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { CssBaseline, ThemeProvider } from '@mui/material'
import App from './App.jsx'
import { AuthProvider } from './auth/AuthContext.jsx'
import theme from './theme.js'
import './index.css'

/**
 * Where the app starts.
 *
 * The providers wrap everything: the theme so components look consistent,
 * the router so pages can link to each other, and AuthProvider so any page can
 * ask who is signed in.
 */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  </StrictMode>,
)
