import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs } from '../../stores'
import { prepareForServerRestart, reloadWhenServerReady } from '../../services/restart'
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

function LoadDialogBody() {
  const closeDialog = useDialogs((s) => s.closeDialog)
  const saveList = useDialogs((s) => s.saveList)
  const [selected, setSelected] = useState<string | null>(null)
  const [restoring, setRestoring] = useState(false)
  const refreshTimer = useRef<number | null>(null)

  // Ask for the current list every time the dialog opens (body mounts).
  useEffect(() => {
    emitC('action', { action: 'listSaves' })
    return () => {
      if (refreshTimer.current !== null) window.clearTimeout(refreshTimer.current)
    }
  }, [])

  const performLoad = async () => {
    if (!selected || restoring) return
    setRestoring(true)
    await prepareForServerRestart()
    emitC('action', { action: 'restoreGame', parameters: { saveFolder: selected } })
    // restore_complete triggers the page reload (see LoadDialog effect below).
  }

  const deleteSelected = () => {
    if (!selected || restoring) return
    if (!window.confirm('Delete this save? This cannot be undone.')) return
    emitC('action', { action: 'deleteSave', parameters: { saveFolder: selected } })
    setSelected(null)
    // Legacy parity: refresh the list shortly after the delete lands.
    refreshTimer.current = window.setTimeout(() => {
      emitC('action', { action: 'listSaves' })
    }, 500)
  }

  const entries = (saveList ?? []).map(toSaveEntry).filter((e) => e.folder !== '')

  return (
    <DialogShell title="Load Saved Game" onClose={closeDialog} maxWidth="500px" legacy>
      <div className="flex flex-col gap-3 font-chrome text-sm">
        <div className="max-h-[400px] overflow-y-auto rounded border border-soft bg-page p-2">
          {saveList === null ? (
            <p className="p-8 text-center text-secondary">Loading save games...</p>
          ) : entries.length === 0 ? (
            <p className="p-8 text-center text-secondary">No save games found.</p>
          ) : (
            entries.map((entry) => {
              const isSelected = entry.folder === selected
              return (
                <button
                  key={entry.folder}
                  type="button"
                  onClick={() => setSelected(entry.folder)}
                  aria-pressed={isSelected}
                  className="mb-2 block w-full cursor-pointer rounded-md border border-card bg-panel p-3 text-left last:mb-0"
                  style={{
                    backgroundColor: isSelected ? 'rgba(76, 175, 80, 0.12)' : undefined,
                    outline: isSelected ? '2px solid var(--accent)' : 'none',
                    outlineOffset: '-2px',
                  }}
                >
                  <div className="flex items-center gap-2">
                        <span className="font-chrome text-base font-bold text-accent">{entry.folder}</span>
                    {entry.mode && (
                      <span
                        className="rounded px-2 py-0.5 text-xs font-bold uppercase"
                        style={{
                          backgroundColor:
                            entry.mode === 'full' ? 'rgba(80, 200, 120, 0.15)' : 'rgba(76, 175, 80, 0.2)',
                          color: 'var(--accent)',
                        }}
                      >
                        {entry.mode}
                      </span>
                    )}
                  </div>
                  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                    <dt className="w-[75px] font-semibold text-[#aaa]">Date:</dt>
                    <dd className="text-[#FFA500]">{entry.date}</dd>
                    <dt className="text-secondary">Module:</dt>
                    <dd className="font-semibold text-accent">{entry.module}</dd>
                    <dt className="text-secondary">Location:</dt>
                    <dd className="text-[#87CEEB]">{entry.location}</dd>
                    {entry.description && (
                      <>
                        <dt className="text-secondary">Notes:</dt>
                        <dd className="font-body text-primary">{entry.description}</dd>
                      </>
                    )}
                  </dl>
                </button>
              )
            })
          )}
        </div>

        {restoring && (
          <p className="text-center font-log text-xs text-accent">
            Restoring save... the page will reload when the server is ready.
          </p>
        )}

        <div className="grid grid-cols-3 gap-2">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button
            type="button"
            className={dialogButtonDanger}
            onClick={deleteSelected}
            disabled={!selected || restoring}
          >
            Delete
          </button>
          <button
            type="button"
            className={dialogButtonPrimary}
            onClick={() => void performLoad()}
            disabled={!selected || restoring}
          >
            Load Game
          </button>
        </div>
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
