import { useEffect, useRef, useState } from 'react'
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
  const connected = useSession((s) => s.connected)
  const [preparing, setPreparing] = useState(false)
  const generation = useRef(0)
  const busy = useRef(false)
  useEffect(() => {
    if (!connected || update.running) {
      generation.current++
      busy.current = false
      setPreparing(false)
    }
    return () => { generation.current++; busy.current = false }
  }, [connected, update.running])
  const requestClose = () => {
    generation.current++
    closeDialog()
  }
  useEffect(() => { if (update.complete) void reloadWhenServerReady() }, [update.complete])
  const proceed = async () => {
    if (busy.current || useDialogs.getState().update.running || !useSession.getState().connected) return
    const attempt = ++generation.current
    const isCurrent = () => attempt === generation.current && useSession.getState().connected
      && useDialogs.getState().open === 'update' && !useDialogs.getState().update.running
    busy.current = true
    setPreparing(true)
    try {
      await prepareForServerRestart(isCurrent)
      if (!isCurrent()) return
      useDialogs.getState().updateStarted()
      emitC('trigger_update', undefined)
    } catch (error) {
      if (!isCurrent()) return
      useDialogs.getState().updateError({
        error: `Update could not start: ${error instanceof Error ? error.message : String(error)}`,
      })
      busy.current = false
      setPreparing(false)
    }
  }
  const currentStatus = preparing ? 'Preparing server restart...' : update.complete
    ? `${update.complete} Please refresh the page.`
    : update.error
      ? `Update failed: ${update.error}`
      : update.log.at(-1) ?? null
  return <DialogShell title={ember ? 'Update Available' : '🔄 Update Available'} onClose={requestClose} maxWidth="700px" legacy>
    <div className="neq-update-content-parity">
      <p>{version ? `A new version is available: v${version.local_version} -> v${version.remote_version}` : 'A new version is available!'}</p>
      <div className="neq-reset-warning-box-parity"><strong>{!ember && '⚠️ '}Backup Recommended</strong><p>Before updating, we recommend backing up your saved games and any custom modules.</p></div>
      {!connected && <p role="status">Disconnected. Reconnect before starting an update.</p>}
      <div className="neq-dialog-buttons-parity"><button type="button" className={dialogButtonPrimary} disabled={!connected || preparing || (ember && update.running)} onClick={() => void proceed()}>Proceed with Update</button><button type="button" className={dialogButtonSecondary} onClick={requestClose}>Cancel</button></div>
      {currentStatus && <div className="neq-update-progress-parity"><p role="status">{currentStatus}</p></div>}
    </div>
  </DialogShell>
}

export function UpdateDialog() { const open = useDialogs((s) => s.open); return open === 'update' ? <UpdateDialogBody /> : null }
