import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'
import { useDialogs, useSession } from '../../stores'
import { DialogShell, dialogButtonPrimary, dialogButtonSecondary } from './DialogShell'
import { useEmberViewport } from '../layout/useEmberViewport'

function UpdateDialogBody() {
  const ember = useEmberViewport()
  const version = useSession((s) => s.version)
  const update = useDialogs((s) => s.update)
  const closeDialog = useDialogs((s) => s.closeDialog)
  useEffect(() => { if (update.complete) void reloadWhenServerReady() }, [update.complete])
  const proceed = async () => {
    // Keep the legacy button visually enabled while preventing duplicate
    // update requests from a rapid second click.
    if (useDialogs.getState().update.running) return
    try {
      await prepareForServerRestart()
      useDialogs.getState().updateStarted()
      emitC('trigger_update', undefined)
    } catch (error) {
      useDialogs.getState().updateError({
        error: `Update could not start: ${error instanceof Error ? error.message : String(error)}`,
      })
    }
  }
  const currentStatus = update.complete
    ? `${update.complete} Please refresh the page.`
    : update.error
      ? `Update failed: ${update.error}`
      : update.log.at(-1) ?? null
  return <DialogShell title={ember ? 'Update Available' : '🔄 Update Available'} onClose={closeDialog} maxWidth="700px" legacy>
    <div className="neq-update-content-parity">
      <p>{version ? `A new version is available: v${version.local_version} -> v${version.remote_version}` : 'A new version is available!'}</p>
      <div className="neq-reset-warning-box-parity"><strong>{!ember && '⚠️ '}Backup Recommended</strong><p>Before updating, we recommend backing up your saved games and any custom modules.</p></div>
      <div className="neq-dialog-buttons-parity"><button type="button" className={dialogButtonPrimary} onClick={() => void proceed()}>Proceed with Update</button><button type="button" className={dialogButtonSecondary} onClick={closeDialog}>Cancel</button></div>
      {currentStatus && <div className="neq-update-progress-parity"><p role="status">{currentStatus}</p></div>}
    </div>
  </DialogShell>
}

export function UpdateDialog() { const open = useDialogs((s) => s.open); return open === 'update' ? <UpdateDialogBody /> : null }
