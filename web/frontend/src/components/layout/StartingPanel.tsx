import { useEffect, useRef } from 'react'
import type { ServerEvents } from '../../contract/events'
import { useLog, useSession } from '../../stores'

const STARTUP_FAILURE_MESSAGE =
  'Startup handoff failed. You can use recovery from settings.'

function startupRecoveryMessage(
  recovery: ServerEvents['startup_recovery_response'],
): { type: 'system' | 'error'; content: string } {
  const status = recovery.status || 'failed'
  if (status === 'recovered') {
    return { type: 'system', content: 'Startup recovery completed. Adventure flow resumed.' }
  }
  if (status === 'already_ready') {
    return { type: 'system', content: 'Startup is already complete.' }
  }
  if (status === 'in_progress') {
    return { type: 'system', content: 'Startup recovery is already in progress.' }
  }
  if (status === 'not_recoverable') {
    return { type: 'error', content: 'Startup recovery not allowed in current state.' }
  }
  const reason = recovery.error ? ` (${recovery.error})` : ''
  const retryHint = recovery.retryAfterSeconds
    ? ` Retry in ${recovery.retryAfterSeconds}s.`
    : ''
  return { type: 'error', content: `Startup recovery failed${reason}.${retryHint}` }
}

/**
 * Mirrors the legacy startup socket handlers.  Legacy keeps the ordinary
 * command row in place and reports failure/recovery outcomes in the game log;
 * it does not render a separate startup or recovery panel.
 */
export function StartingPanel() {
  const startupStatus = useSession((state) => state.startupStatus)
  const startupAttemptId = useSession((state) => state.startupAttemptId)
  const recovery = useSession((state) => state.recovery)
  const append = useLog((state) => state.append)
  const previousStatus = useRef(startupStatus)
  const previousRecovery = useRef(recovery)

  useEffect(() => {
    const changedToFailure =
      previousStatus.current !== 'failed' && startupStatus === 'failed'
    previousStatus.current = startupStatus
    if (!changedToFailure) return

    append({
      type: 'error',
      content: STARTUP_FAILURE_MESSAGE,
      message_id: `startup-failure-${startupAttemptId || 'current'}`,
    })
  }, [append, startupAttemptId, startupStatus])

  useEffect(() => {
    const changed = previousRecovery.current !== recovery
    previousRecovery.current = recovery
    if (!changed || !recovery) return

    const message = startupRecoveryMessage(recovery)
    append({
      ...message,
      message_id: [
        'startup-recovery',
        startupAttemptId || 'current',
        recovery.status || 'failed',
        recovery.error || '',
        recovery.retryAfterSeconds || '',
      ].join('-'),
    })
  }, [append, recovery, startupAttemptId])

  return null
}
