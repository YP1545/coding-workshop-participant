import { Alert, Box, Step, StepLabel, Stepper, Typography } from '@mui/material'
import { WORKFLOW_STEPS, label } from '../constants'

/**
 * Shows where an incident has got to, as a stepper.
 *
 * Part of: frontend / incidents.
 *
 * This is the "visual representation of the ticket workflow" the brief asks
 * for — not just a coloured chip saying the status.
 *
 * Blocked is handled separately rather than as a fifth step. An incident is
 * blocked *while* it is in progress, so showing it in the line would suggest
 * work moves forward into being stuck, which is not what happened.
 */
export default function WorkflowStepper({ incident }) {
  const isBlocked = incident.status === 'blocked'

  // A blocked incident sits at the in-progress point of the line, because that
  // is the step it will return to once it is unblocked.
  const currentStatus = isBlocked ? 'in_progress' : incident.status
  const activeStep = WORKFLOW_STEPS.indexOf(currentStatus)

  return (
    <Box>
      <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: isBlocked ? 2 : 0 }}>
        {WORKFLOW_STEPS.map((step) => (
          <Step key={step} completed={WORKFLOW_STEPS.indexOf(step) < activeStep}>
            <StepLabel error={isBlocked && step === 'in_progress'}>
              <Typography variant="body2">{label(step)}</Typography>
            </StepLabel>
          </Step>
        ))}
      </Stepper>

      {isBlocked && (
        <Alert severity="error">
          <strong>Blocked:</strong> {incident.blocked_reason || 'no reason given'}
        </Alert>
      )}
    </Box>
  )
}
