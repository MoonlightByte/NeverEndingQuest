import { useEffect, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useLog } from '../../stores'
import { DialogShell, dialogButtonDanger, dialogButtonSecondary } from './DialogShell'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'

/** Legacy-compatible five-digit confirmation code (10000-99999). */
export function generateResetCode(): string {
  const value = new Uint32Array(1)
  crypto.getRandomValues(value)
  return String(10000 + (value[0] % 90000))
}

const RESET_ACTIONS = [
  'Creates a timestamped backup of your current progress',
  'Deletes all characters, conversations, and game state',
  'Restores modules from clean system templates',
  'Returns the game to first-time startup state',
  'Preserves system files and module templates',
]

/** Body unmounts on close, so every open generates a fresh confirmation code. */
function ResetDialogBody() {
  const closeDialog = useDialogs((s) => s.closeDialog)
  const [code] = useState(() => generateResetCode())
  const [typed, setTyped] = useState('')

  const confirmed = typed === code

  const performReset = async () => {
    if (!confirmed) return
    useLog.getState().append({
      type: 'info',
      content:
        'Campaign reset initiated... The application may become unresponsive while the server restarts.',
    })
    await prepareForServerRestart()
    emitC('action', { action: 'nuclearReset', parameters: {} })
    closeDialog()
  }

  return (
    <DialogShell title={<><span className="text-[#f44336]">⚠️</span> CAMPAIGN RESET <span className="text-[#f44336]">⚠️</span></>} onClose={closeDialog} maxWidth="750px" legacy>
      <div className="font-chrome text-sm leading-[normal]">
        <div className="mb-5">
          <div className="mb-[15px] rounded-md border-2 border-[#f44336] bg-[#4a1515] p-[15px] text-center">
            <strong className="mb-2 block text-base text-[#f44336]">🔥 WARNING: Complete Campaign Wipe</strong>
            <p className="m-0 text-sm text-[#ffcdd2]">
            This will permanently delete your current game progress and return to a fresh
            campaign start.
            </p>
          </div>

          <div className="mb-[15px] rounded-md border border-[#4caf50] bg-[#1a2a1a] p-[15px]">
            <h4 className="mb-[10px] text-[15px] font-bold text-accent">📋 What This Reset Does:</h4>
            <ul className="m-0 list-none p-0 text-primary">
              {RESET_ACTIONS.map((line, index) => (
                <li key={line} className="py-[3px] text-[13px]">{['✅','🗑️','🔄','🏁','🔒'][index]} {line}</li>
              ))}
            </ul>
          </div>

          <p className="rounded border-l-4 border-accent bg-[#2d4a2d] p-3 text-[13px] text-[#c8e6c9]">
            <strong className="text-accent">💡 Note:</strong> Your current progress will be backed up to{' '}
            <code className="rounded bg-page px-1.5 py-0.5 font-log text-[#ffd54f]">modules/backups/campaign_backup_[timestamp]</code>{' '}
            before reset. Module restore points (BU files) are protected and remain intact.
          </p>
        </div>

        <div className="mb-5 text-center">
          <p className="text-secondary">To confirm, please type the following code into the box below:</p>
          <p
            data-testid="reset-code"
            className="my-[10px] select-none rounded bg-page p-[5px] font-log text-2xl font-bold text-accent"
            style={{ letterSpacing: '5px' }}
          >
            {code}
          </p>
          <input
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value.replace(/\D/g, '').slice(0, 5))}
            inputMode="numeric"
            placeholder="Enter code here"
            aria-label="Reset confirmation code"
            autoComplete="off"
            className="w-full rounded border border-[#555] bg-[#333] p-2 text-center font-chrome text-lg text-primary outline-none focus:border-accent"
          />
        </div>

        <div className="mt-6 flex justify-between gap-[10px]">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button
            type="button"
            className={dialogButtonDanger}
            onClick={() => void performReset()}
            disabled={!confirmed}
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
