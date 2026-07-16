import { useEffect, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useLog } from '../../stores'
import { DialogShell, dialogButtonDanger, dialogButtonSecondary } from './DialogShell'

/** Unambiguous ASCII charset (no 0/O, 1/I/L) for the confirmation code. */
const CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
const CODE_LENGTH = 6

/** Random 6-char confirmation code (rejection sampling, no modulo bias). */
export function generateResetCode(): string {
  const limit = Math.floor(256 / CODE_CHARS.length) * CODE_CHARS.length
  let out = ''
  while (out.length < CODE_LENGTH) {
    const buf = new Uint8Array(CODE_LENGTH * 2)
    crypto.getRandomValues(buf)
    for (const byte of buf) {
      if (byte < limit && out.length < CODE_LENGTH) {
        out += CODE_CHARS[byte % CODE_CHARS.length]
      }
    }
  }
  return out
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

  const performReset = () => {
    if (!confirmed) return
    useLog.getState().append({
      type: 'info',
      content:
        'Campaign reset initiated... The application may become unresponsive while the server restarts.',
    })
    emitC('action', { action: 'nuclearReset', parameters: {} })
    closeDialog()
  }

  return (
    <DialogShell title="CAMPAIGN RESET" onClose={closeDialog} maxWidth="36rem">
      <div className="flex flex-col gap-3 font-chrome text-sm">
        <div className="rounded border-2 border-[#c0392b] bg-page p-3">
          <strong className="text-[#e74c3c]">WARNING: Complete Campaign Wipe</strong>
          <p className="mt-1 text-secondary">
            This will permanently delete your current game progress and return to a fresh
            campaign start.
          </p>
        </div>

        <div className="rounded border-2 border-card bg-page p-3">
          <strong className="text-primary">What this reset does:</strong>
          <ul className="mt-2 list-disc pl-5 text-secondary">
            {RESET_ACTIONS.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-secondary">
          Note: your current progress is backed up to{' '}
          <code className="font-log">modules/backups/campaign_backup_[timestamp]</code> before
          the reset. Module restore points (BU files) remain intact.
        </p>

        <div className="text-center">
          <p className="text-secondary">To confirm, type the following code into the box below:</p>
          <p
            data-testid="reset-code"
            className="mx-auto my-2 select-none rounded bg-page px-3 py-1 font-log text-2xl font-bold text-accent"
            style={{ letterSpacing: '5px', maxWidth: '14rem' }}
          >
            {code}
          </p>
          <input
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value.toUpperCase())}
            placeholder="Enter code here"
            aria-label="Reset confirmation code"
            autoComplete="off"
            className="w-full rounded border-2 border-card bg-page px-3 py-2 text-center font-log text-lg text-primary outline-none focus:border-accent"
          />
        </div>

        <div className="flex justify-end gap-2">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button
            type="button"
            className={dialogButtonDanger}
            onClick={performReset}
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
      window.location.reload()
    }
  }, [actionResult])

  if (open !== 'reset') return null
  return <ResetDialogBody />
}
