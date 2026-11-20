import { useDialogs, useSession } from '../stores'
import { useAllowance } from '../stores/allowance'
import { allowanceLine, allowanceLocked } from '../components/layout/allowanceText'

/** Shared gate for command entry and typed roll submission. */
export function useComposerGating() {
  const connected = useSession(s => s.connected)
  const mode = useSession(s => s.mode)
  const startupStatus = useSession(s => s.startupStatus)
  const startupInputReady = useSession(s => s.startupInputReady)
  const inputAuthorized = useSession(s => s.inputAuthorized)
  const isProcessing = useSession(s => s.isProcessing)
  const restorePending = useSession(s => s.restorePending)
  const recoveryRequired = useSession(s => s.restoreRecoveryRequired)
  const action = useDialogs(s => s.actionResult)
  // #2072: a hosted player whose free play is used or paused cannot start a turn.
  const allowance = useAllowance(s => s.value)
  const allowanceLock = allowanceLocked(allowance)
  const restoreRestartPending = action?.kind === 'restore' && action.can_resume !== false && action.restart_required !== false
  const startupStillLocks = mode === 'starting' && startupStatus !== 'failed'
    && !(startupStatus === 'in_progress' && startupInputReady)
  const locked = action?.kind === 'exit' || action?.kind === 'reset' || restoreRestartPending || recoveryRequired || restorePending
    || isProcessing || !connected || mode === 'disconnected' || startupStillLocks || allowanceLock
  return { locked, canSend: !locked && inputAuthorized, allowanceLine: allowanceLock ? allowanceLine(allowance) : null }
}
