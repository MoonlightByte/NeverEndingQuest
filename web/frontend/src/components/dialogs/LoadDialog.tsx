import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useLog, useSession } from '../../stores'
import { ConfirmDialog } from './ConfirmDialog'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'
import { useEmberViewport } from '../layout/useEmberViewport'
import {
  DialogShell,
  dialogButtonDanger,
  dialogButtonPrimary,
  dialogButtonSecondary,
} from './DialogShell'

interface SaveEntry {
  folder: string
  mode: string
  date: string
  module: string
  location: string
  description: string
}

function asString(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  return ''
}

function toSaveEntry(raw: Record<string, unknown>): SaveEntry {
  const gameState =
    typeof raw['game_state'] === 'object' && raw['game_state'] !== null
      ? (raw['game_state'] as Record<string, unknown>)
      : {}
  return {
    folder: asString(raw['save_folder']),
    mode: asString(raw['save_mode']),
    date: asString(raw['save_date_readable']) || 'Unknown',
    module: asString(raw['module']) || 'Unknown Module',
    location: asString(gameState['current_location']) || 'Unknown Location',
    description: asString(raw['description']),
  }
}

const saveExists = (folder: string) => useDialogs.getState().saveList?.some(entry => asString(entry['save_folder']) === folder) === true

function LoadDialogBody() {
  const ember = useEmberViewport()
  const closeDialog = useDialogs((s) => s.closeDialog)
  const saveList = useDialogs((s) => s.saveList)
  const [selected, setSelected] = useState<string | null>(null)
  const [restoring, setRestoring] = useState(false)
  const [restoreError, setRestoreError] = useState('')
  const connected = useSession((s) => s.connected)
  const [confirmation, setConfirmation] = useState<{ kind: 'load' | 'delete'; folder: string } | null>(null)
  const operation = useRef(0)
  const busy = useRef(false)
  const cancelConfirmation = () => {
    operation.current++
    busy.current = false
    setRestoring(false)
    setConfirmation(null)
  }
  useEffect(() => {
    if (!connected) cancelConfirmation()
    return () => { operation.current++; busy.current = false }
  }, [connected])
  useEffect(() => {
    if (selected && !saveExists(selected)) setSelected(null)
    if (confirmation && !saveExists(confirmation.folder)) cancelConfirmation()
  }, [saveList, selected, confirmation])
  const refreshTimer = useRef<number | null>(null)

  // Ask for the current list every time the dialog opens (body mounts).
  useEffect(() => {
    if (useSession.getState().connected) emitC('action', { action: 'listSaves' })
    return () => {
      if (refreshTimer.current !== null) window.clearTimeout(refreshTimer.current)
    }
  }, [])

  const performLoad = async (folder: string) => {
    if (busy.current || !useSession.getState().connected || !saveExists(folder)) return
    const ticket = ++operation.current
    busy.current = true
    setRestoring(true)
    setRestoreError('')
    try {
      await prepareForServerRestart(() => ticket === operation.current && useSession.getState().connected && saveExists(folder))
      if (ticket !== operation.current || !useSession.getState().connected || !saveExists(folder)) {
        return
      }
      emitC('action', { action: 'restoreGame', parameters: { saveFolder: folder } })
      closeDialog()
      // restore_complete triggers the page reload (see LoadDialog effect below).
    } catch (error) {
      if (ticket !== operation.current) return
      setRestoreError(`Game restore could not start: ${error instanceof Error ? error.message : String(error)}`)
      useLog.getState().append({
        type: 'error',
        content: `Game restore could not start: ${error instanceof Error ? error.message : String(error)}`,
      })
      setRestoring(false)
      busy.current = false
    }
  }

  const deleteSelected = (folder: string) => {
    if (busy.current || !useSession.getState().connected || !saveExists(folder)) return
    busy.current = true
    emitC('action', { action: 'deleteSave', parameters: { saveFolder: folder } })
    setConfirmation(null)
    setSelected(null)
    // Legacy parity: refresh the list shortly after the delete lands.
    refreshTimer.current = window.setTimeout(() => {
      busy.current = false
      if (useSession.getState().connected) emitC('action', { action: 'listSaves' })
    }, 500)
  }

  const entries = (saveList ?? []).map(toSaveEntry).filter((e) => e.folder !== '')
  const requestConfirmation = (kind: 'load' | 'delete') => {
    if (!selected || busy.current || !useSession.getState().connected || !saveExists(selected)) return
    setRestoreError('')
    if (ember) setConfirmation({ kind, folder: selected })
    else if (window.confirm(kind === 'load' ? 'This will restore the selected save and restart the server. Your current progress will be lost. Continue?' : 'Delete this save? This cannot be undone.')) {
      if (kind === 'load') void performLoad(selected)
      else deleteSelected(selected)
    }
  }

  return (
    <DialogShell title="Load Saved Game" onClose={closeDialog} maxWidth="700px" legacy>
      <div>
        <div className="neq-save-list-parity">
          {saveList === null ? (
            <p className="neq-save-list-empty-parity">Loading...</p>
          ) : entries.length === 0 ? (
            <p className="neq-save-list-empty-parity">No save games found.</p>
          ) : (
            entries.map((entry) => {
              const isSelected = entry.folder === selected
              return (
                <button
                  key={entry.folder}
                  type="button"
                  onClick={() => setSelected(entry.folder)}
                  aria-pressed={isSelected}
                  className="neq-save-item-parity"
                >
                  <div className="neq-save-item-header-parity">
                    {entry.folder}
                    {entry.mode && (
                      <span className={`neq-save-mode-badge-parity ${entry.mode === 'full' ? 'full' : 'essential'}`}>
                        {entry.mode}
                      </span>
                    )}
                  </div>
                  <div>
                    <div className="neq-save-detail-row-parity"><span className="neq-save-detail-label-parity">Date:</span><span className="neq-save-detail-value-parity date">{entry.date}</span></div>
                    <div className="neq-save-detail-row-parity"><span className="neq-save-detail-label-parity">Module:</span><span className="neq-save-detail-value-parity module">{entry.module}</span></div>
                    <div className="neq-save-detail-row-parity"><span className="neq-save-detail-label-parity">Location:</span><span className="neq-save-detail-value-parity location">{entry.location}</span></div>
                    {entry.description && (
                      <div className="neq-save-detail-row-parity"><span className="neq-save-detail-label-parity">Notes:</span><span className="neq-save-detail-value-parity description">{entry.description}</span></div>
                    )}
                  </div>
                </button>
              )
            })
          )}
        </div>

        {restoring && (
          <p className="mt-3 text-center font-log text-xs text-accent">
            Restoring save... the page will reload when the server is ready.
          </p>
        )}

        <div className="neq-dialog-buttons-parity">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button
            type="button"
            className={dialogButtonDanger}
            onClick={() => requestConfirmation('delete')}
            disabled={!selected || restoring || !connected}
          >
            Delete
          </button>
          <button
            type="button"
            className={dialogButtonPrimary}
            onClick={() => requestConfirmation('load')}
            disabled={!selected || restoring || !connected}
          >
            Load Game
          </button>
        </div>
        {confirmation && <ConfirmDialog
          title={confirmation.kind === 'load' ? 'Restore Saved Game' : 'Delete Saved Game'}
          message={confirmation.kind === 'load' ? 'This will restore the selected save and restart the server. Your current progress will be lost. Continue?' : 'Delete this save? This cannot be undone.'}
          confirmLabel={confirmation.kind === 'load' ? 'Restore Game' : 'Delete Save'}
          pending={restoring} error={restoreError} disabled={!connected} onCancel={cancelConfirmation}
          onConfirm={() => confirmation.kind === 'load' ? void performLoad(confirmation.folder) : deleteSelected(confirmation.folder)}
        />}
      </div>
    </DialogShell>
  )
}

/**
 * Load dialog: action listSaves -> save_list_response; Load emits restoreGame and
 * reloads the page on restore_complete; Delete emits deleteSave (plan 4.4e).
 */
export function LoadDialog() {
  const open = useDialogs((s) => s.open)
  const actionResult = useDialogs((s) => s.actionResult)

  // restore_complete lands in the dialogs store as an actionResult; the server
  // restarts itself after emitting it, so the client reloads to reattach.
  useEffect(() => {
    if (actionResult?.kind === 'restore') {
      void reloadWhenServerReady()
    }
  }, [actionResult])

  if (open !== 'load') return null
  return <LoadDialogBody />
}
