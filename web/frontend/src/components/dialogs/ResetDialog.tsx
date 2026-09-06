import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useLog } from '../../stores'
import { DialogShell, dialogButtonDanger, dialogButtonSecondary } from './DialogShell'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'
import { useEmberViewport } from '../layout/useEmberViewport'

/** Legacy-compatible five-digit confirmation code (10000-99999). */
export function generateResetCode(): string {
  return String(Math.floor(10000 + Math.random() * 90000))
}

const RESET_ACTIONS = [
  'Creates timestamped backup of your current progress',
  'Deletes all characters, conversations, and game state',
  'Restores modules from clean system templates',
  'Returns game to first-time startup state',
  'Preserves system files and module templates',
]

/** Body unmounts on close, so every open generates a fresh confirmation code. */
function ResetDialogBody() {
  const ember = useEmberViewport()
  const closeDialog = useDialogs((s) => s.closeDialog)
  const [code] = useState(() => generateResetCode())
  const [typed, setTyped] = useState('')
  const [resetting, setResetting] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const confirmed = typed === code

  const performReset = async () => {
    if (!confirmed || resetting) return
    setResetting(true)
    useLog.getState().append({
      type: 'info',
      content:
        'Campaign reset initiated... The application may become unresponsive while the server restarts.',
    })
    try {
      await prepareForServerRestart()
      useDialogs.getState().setActionResult({
        kind: 'reset',
        message: 'Campaign reset initiated. Waiting for the server to restart.',
      })
      emitC('action', { action: 'nuclearReset', parameters: {} })
      closeDialog()
    } catch (error) {
      useLog.getState().append({
        type: 'error',
        content: `Campaign reset could not start: ${error instanceof Error ? error.message : String(error)}`,
      })
      setResetting(false)
    }
  }

  return (
    <DialogShell title={ember ? 'Campaign Reset' : <><span className="text-[#f44336]">⚠️</span> CAMPAIGN RESET <span className="text-[#f44336]">⚠️</span></>} onClose={closeDialog} maxWidth="750px" legacy className="neq-reset-dialog-parity" initialFocusRef={inputRef}>
      <div>
        <div className="neq-reset-warning-container-parity">
          <div className="neq-reset-warning-box-parity">
            <strong>{!ember && '🔥 '}WARNING: Complete Campaign Wipe</strong>
            <p>
            This will permanently delete your current game progress and return to a fresh
            campaign start.
            </p>
          </div>

          <div className="neq-reset-info-box-parity">
            <h4>{!ember && '📋 '}What This Reset Does:</h4>
            <ul className="neq-reset-action-list-parity">
              {RESET_ACTIONS.map((line, index) => (
                <li key={line}>{`${ember ? '•' : ['✅','🗑️','🔄','🏁','🔒'][index]} ${line}`}</li>
              ))}
            </ul>
          </div>

          <div className="neq-reset-note-box-parity">
            <strong>{!ember && '💡 '}Note:</strong> Your current progress will be backed up to{' '}
            <code>modules/backups/campaign_backup_[timestamp]</code>{' '}
            before reset. Module restore points (BU files) are protected and remain intact.
          </div>
        </div>

        <div className="neq-reset-confirmation-parity">
          <p>To confirm, please type the following code into the box below:</p>
          <p
            data-testid="reset-code"
            className="neq-reset-code-parity"
          >
            {code}
          </p>
          <input
            ref={inputRef}
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value.replace(/\D/g, '').slice(0, 5))}
            disabled={resetting}
            inputMode="numeric"
            placeholder="Enter code here"
            aria-label="Reset confirmation code"
            autoComplete="off"
            className="neq-reset-input-parity"
          />
        </div>

        <div className="neq-dialog-buttons-parity">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog} disabled={resetting}>
            Cancel
          </button>
          <button
            type="button"
            className={dialogButtonDanger}
            onClick={() => void performReset()}
            disabled={!confirmed || resetting}
          >
            Confirm Reset
          </button>
        </div>
      </div>
    </DialogShell>
  )
}

/**
 * Nuclear reset dialog: warning + random 6-char confirmation code the user must
 * retype before action nuclearReset is emitted (plan 4.4e).
 */
export function ResetDialog() {
  const open = useDialogs((s) => s.open)
  const actionResult = useDialogs((s) => s.actionResult)

  // reset_complete -> the server restarts itself; reload to reattach.
  useEffect(() => {
    if (actionResult?.kind === 'reset') {
      void reloadWhenServerReady()
    }
  }, [actionResult])

  if (open !== 'reset') return null
  return <ResetDialogBody />
}
