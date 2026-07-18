import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'
import { useDialogs, useSession } from '../../stores'
import { DialogShell, dialogButtonPrimary, dialogButtonSecondary } from './DialogShell'

function UpdateDialogBody() {
  const version = useSession((s) => s.version)
  const update = useDialogs((s) => s.update)
  const closeDialog = useDialogs((s) => s.closeDialog)
  useEffect(() => { if (update.complete) void reloadWhenServerReady() }, [update.complete])
  const proceed = async () => { await prepareForServerRestart(); useDialogs.getState().updateStarted(); emitC('trigger_update', undefined) }
  return <DialogShell title="🔄 Update Available" onClose={closeDialog} maxWidth="500px" legacy>
    <div className="font-chrome text-sm text-primary">
      <p>{version ? `A new version is available: v${version.local_version} -> v${version.remote_version}` : 'A new version is available!'}</p>
      <div className="my-4 rounded-md border-2 border-[#f44336] bg-[#4a1515] p-4 text-center"><strong className="block text-[#f44336]">⚠️ Backup Recommended</strong><p className="text-[#ffcdd2]">Before updating, we recommend backing up your saved games and any custom modules.</p></div>
      <div className="grid grid-cols-2 gap-2"><button type="button" className={dialogButtonPrimary} disabled={update.running} onClick={() => void proceed()}>Proceed with Update</button><button type="button" className={dialogButtonSecondary} disabled={update.running} onClick={closeDialog}>Cancel</button></div>
      {(update.running || update.log.length > 0 || update.error || update.complete) && <div className="mt-5 rounded border border-card bg-page p-3 font-log text-xs" role="status">{update.log.map((line, index) => <div key={`${line}-${index}`}>{line}</div>)}{update.error && <div className="text-red-400">{update.error}</div>}{update.complete && <div className="text-accent">{update.complete}</div>}</div>}
    </div>
  </DialogShell>
}

export function UpdateDialog() { const open = useDialogs((s) => s.open); return open === 'update' ? <UpdateDialogBody /> : null }
