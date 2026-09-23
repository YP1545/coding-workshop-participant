import { createTheme } from '@mui/material/styles'

/**
 * Application theme: the colours, type and control sizes the whole app shares.
 *
 * Part of: frontend / shared.
 *
 * Why its own file: the alternative is each page picking its own sizes and
 * greys, which is how an app ends up with three sizes of button and four
 * shades of border. Setting the defaults here means a rule is applied once and
 * cannot be forgotten on the next page.
 *
 * Two rules are doing most of the work:
 *
 *   - Control sizes follow Apple's UI design guidance
 *     (https://developer.apple.com/design/tips/), which is written in points.
 *     On iOS one point is one CSS pixel, so 44pt becomes 44px: every control is
 *     at least 44x44 so it can be tapped accurately. MUI's own defaults are
 *     smaller — a Button is 37px tall, an IconButton 40, a pagination item 32 —
 *     so they are raised here rather than in each component.
 *
 *   - Surfaces are separated by a hairline border rather than a shadow. A page
 *     of cards that all float looks busy; a page of cards that sit flat on a
 *     tinted background reads as one surface with sections.
 */

// Apple's minimum tappable size, named because several rules below use it.
const TOUCH_TARGET = 44

// The dark rail down the left. Kept here rather than in AppLayout so the
// drawer, the desktop sidebar and anything added later cannot drift apart.
export const SIDEBAR = {
  width: 264,
  bg: '#101828',
  text: '#98A2B3',
  textActive: '#FFFFFF',
  activeBg: '#1570EF',
  hoverBg: 'rgba(255, 255, 255, 0.06)',
  border: 'rgba(255, 255, 255, 0.08)',
}

// One border colour for every card, table row and divider.
export const BORDER = '#E4E7EC'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1570EF' },
    secondary: { main: '#00796b' },
    background: {
      // A faintly blue grey rather than pure white, so a white card has an edge
      // even where its border is hidden behind something.
      default: '#F8FAFC',
      paper: '#FFFFFF',
    },
    divider: BORDER,
    text: {
      primary: '#101828',
      // MUI's default secondary is rgba(0,0,0,0.6) — 4.6:1 on white, over the
      // 4.5:1 line but only just, and it carries the caption under every
      // dashboard figure. This is about 6:1 and still reads as secondary.
      secondary: '#667085',
    },
  },

  shape: { borderRadius: 10 },

  typography: {
    fontFamily: [
      // The system stack: no web font to download, and the app matches whatever
      // the reader's device already uses for its own interface.
      '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto',
      '"Helvetica Neue"', 'Arial', 'sans-serif',
    ].join(','),
    h1: { fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.02em' },
    h2: { fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.01em' },
    h3: { fontSize: '1.05rem', fontWeight: 600 },
    // "Improve legibility by increasing line height" — the default 1.43 is
    // tight for note threads and incident descriptions, the longest text here.
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.6 },
    // 12px clears the 11px floor but only just, and this style carries the
    // captions explaining what each dashboard number means.
    caption: { fontSize: '0.8125rem', lineHeight: 1.5 },
  },

  components: {
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          minHeight: TOUCH_TARGET,
          // All caps reads as shouting at this size, and sentence case is
          // easier to scan when several buttons sit in a row.
          textTransform: 'none',
          fontWeight: 600,
          // A taller button gives a two-word label room to wrap, which looks
          // like a rendering fault ("Sign / out"). Labels here are short
          // enough that one line always fits.
          whiteSpace: 'nowrap',
        },
      },
    },

    MuiIconButton: {
      styleOverrides: { root: { minWidth: TOUCH_TARGET, minHeight: TOUCH_TARGET } },
    },

    // Pagination is the control most used on a phone and MUI's smallest at
    // 32px. Width is a minimum so a two-digit page number still fits.
    MuiPaginationItem: {
      styleOverrides: { root: { minWidth: TOUCH_TARGET, height: TOUCH_TARGET } },
    },

    MuiListItemButton: { styleOverrides: { root: { minHeight: TOUCH_TARGET } } },
    MuiMenuItem: { styleOverrides: { root: { minHeight: TOUCH_TARGET } } },
    MuiTab: { styleOverrides: { root: { minHeight: TOUCH_TARGET, textTransform: 'none' } } },

    MuiChip: {
      defaultProps: { size: 'small' },
      styleOverrides: {
        // Only a chip that does something needs to be tappable. A count chip is
        // a label, and giving every one a 44px box turns a row of them into a
        // ladder of mostly empty space.
        clickable: { minHeight: TOUCH_TARGET },
        root: { fontWeight: 600, backgroundColor: '#F2F4F7', color: '#344054' },
        // MUI's coloured chips are solid, which is too loud when six of them
        // sit in a row on a white card. These are the same tints StatusChip
        // uses, so a green here and a green there mean the same thing.
        colorSuccess: { backgroundColor: '#ECFDF3', color: '#027A48' },
        colorWarning: { backgroundColor: '#FFFAEB', color: '#B54708' },
        colorError: { backgroundColor: '#FEF3F2', color: '#B42318' },
        colorInfo: { backgroundColor: '#EFF8FF', color: '#175CD3' },
      },
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: { minHeight: TOUCH_TARGET, backgroundColor: '#FFFFFF' },
      },
    },

    MuiCard: {
      // A border instead of a shadow — see the file header.
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { border: `1px solid ${BORDER}` },
      },
    },
    MuiPaper: {
      styleOverrides: {
        // Only flat papers get the border; a Menu or Dialog still floats,
        // because it genuinely is above the page.
        elevation0: { border: `1px solid ${BORDER}` },
      },
    },

    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: BORDER },
        head: {
          fontWeight: 600,
          fontSize: '0.8125rem',
          color: '#667085',
          backgroundColor: '#F9FAFB',
        },
      },
    },

    MuiLink: {
      styleOverrides: { root: { textUnderlineOffset: '0.2em', fontWeight: 600 } },
    },
  },
})

export default theme
