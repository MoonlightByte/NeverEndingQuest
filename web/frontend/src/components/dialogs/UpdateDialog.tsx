/**
 * UpdateDialog (plan 4.4e, local edition) -- shown from the HeaderBar version
 * badge when version_status reports update_available. Informational only:
 * trigger_update is operator/toolkit scope (plan scope rules), so the player
 * app tells the operator where to update instead of emitting it.
 */
import { useDialogs, useSession } from '../../stores'
import { DialogShell, dialogButtonPrimary } from './DialogShell'

function UpdateDialogBody() {
  const version = useSession((s) => s.version)
  const closeDialog = useDialogs((s) => s.closeDialog)

  return (
    <DialogShell title="Game Update" onClose={closeDialog}>
      <div className="flex flex-col gap-3 font-body text-sm text-primary">
        {version ? (
          <>
            <p>{version.message}</p>
            <div className="rounded border-2 border-card bg-page p-3 font-log text-xs">
              <div>
                Installed version: <span className="text-accent">{version.local_version}</span>
              </div>
              <div>
                Latest version: <span className="text-accent">{version.remote_version}</span>
              </div>
            </div>
            {version.update_available ? (
              <p className="text-secondary">
                An update is available. Pull the latest release (git pull or the updater script)
                and restart the server to apply it.
              </p>
            ) : (
              <p className="text-secondary">You are running the latest version.</p>
            )}
          </>
        ) : (
          <p className="text-secondary">No version information received from the server yet.</p>
        )}
        <div className="mt-1 flex justify-end">
          <button type="button" className={dialogButtonPrimary} onClick={closeDialog}>
            Close
          </button>
        </div>
      </div>
    </DialogShell>
  )
}

/** Self-gating on the dialogs store, like every other dialog. */
export function UpdateDialog() {
  const open = useDialogs((s) => s.open)
  if (open !== 'update') return null
  return <UpdateDialogBody />
}
