import { Box, Card, CardContent, Stack, Typography } from '@mui/material'

/**
 * One number with a label and an icon, for the dashboard.
 *
 * Part of: frontend / dashboard.
 *
 * The icon is not decoration: four cards of identical grey text are read left
 * to right every time, whereas a tinted icon gives each one a shape you learn
 * after a day and can then find without reading.
 *
 * @param {string} title What the number counts.
 * @param {number|string} value The number itself.
 * @param {string} [caption] A short line explaining what is included.
 * @param {React.ElementType} [icon] A MUI icon component.
 * @param {string} [tone] Background/foreground pair for the icon, from TONES.
 */
export default function StatCard({ title, value, caption, icon: Icon, tone }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        {/* Two cards fit across a phone, which leaves about 170px each — not
            enough for an icon and a label side by side without the label
            breaking onto three lines. Stacking gives the text the full width. */}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={{ xs: 1, sm: 2 }}
               sx={{ alignItems: 'flex-start' }}>
          {Icon && (
            <Box
              sx={{
                // Fixed square so the text beside it starts at the same place
                // on every card, whatever the icon.
                flexShrink: 0,
                width: 44,
                height: 44,
                borderRadius: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: tone?.bg || '#F2F4F7',
                color: tone?.fg || '#344054',
              }}
            >
              <Icon fontSize="small" />
            </Box>
          )}

          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
            <Typography variant="h1" component="p" sx={{ my: 0.5 }}>
              {value}
            </Typography>
            {caption && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                {caption}
              </Typography>
            )}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}
