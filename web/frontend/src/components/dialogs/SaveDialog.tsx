import { useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs } from '../../stores'
import { DialogShell, dialogButtonPrimary, dialogButtonSecondary } from './DialogShell'

type SaveMode = 'essential' | 'full'

interface ModeInfo {
  title: string
  badge: string
  includes: string[]
  note: string
}

const MODE_INFO: Record<SaveMode, ModeInfo> = {
  essential: {
    title: 'Game State Save',
    badge: 'RECOMMENDED',
    includes: [
      'Character progress and inventory',
      'Story progress and quest states',
      'Party location and module data',
      'All conversation history',
      'Active encounters and game state',
    ],
    note: 'Perfect for regular gameplay saves. Faster and smaller file size.',
  },
  full: {
    title: 'Archive Edition Save',
    badge: 'COMPLETE ARCHIVE',
    includes: [
      'Everything from the Game State save',
      'Extended conversation archives',
      'Detailed combat logs and analysis',
      'Campaign transition summaries',
      'Historical data for review',
    ],
    note: 'Ideal for campaign analysis or long-term archival. Larger file size.',
  },
}

/** Body unmounts when the dialog closes, so each open starts with a fresh form. */
function SaveDialogBody() {
  const [description, setDescription] = useState('')
  const [saveMode, setSaveMode] = useState<SaveMode>('essential')
  const closeDialog = useDialogs((s) => s.closeDialog)

  const performSave = () => {
    emitC('action', {
      action: 'saveGame',
      parameters: { description: description.trim(), saveMode },
    })
    closeDialog()
  }

  const info = MODE_INFO[saveMode]

  return (
    <DialogShell title="Save Game" onClose={closeDialog}>
      <div className="flex flex-col gap-3 font-chrome text-sm">
        <label htmlFor="save-description" className="text-secondary">
          Description (optional):
        </label>
        <textarea
          id="save-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Enter a brief description of your current progress..."
          rows={3}
          className="w-full resize-y rounded border-2 border-card bg-page px-3 py-2 font-body text-sm text-primary outline-none focus:border-accent"
        />

        <label htmlFor="save-mode" className="text-secondary">
          Save Type:
        </label>
        <select
          id="save-mode"
          value={saveMode}
          onChange={(e) => setSaveMode(e.target.value as SaveMode)}
          className="w-full rounded border-2 border-card bg-page px-2 py-2 font-chrome text-sm text-primary outline-none focus:border-accent"
        >
          <option value="essential">Game State - Complete Save (Recommended)</option>
          <option value="full">Archive Edition - Includes Historical Data</option>
        </select>

        <div className="rounded border-2 border-card bg-page p-3">
          <div className="flex items-center gap-2">
            <strong className="text-primary">{info.title}</strong>
            <span
              className="rounded px-2 py-0.5 text-xs font-bold"
              style={{
                backgroundColor: saveMode === 'essential' ? 'rgba(76, 175, 80, 0.2)' : 'rgba(80, 200, 120, 0.15)',
                color: 'var(--accent)',
              }}
            >
              {info.badge}
            </span>
          </div>
          <ul className="mt-2 list-disc pl-5 text-secondary">
            {info.includes.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-secondary">{info.note}</p>
        </div>

        <div className="mt-1 flex justify-end gap-2">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button type="button" className={dialogButtonPrimary} onClick={performSave}>
            Save Game
          </button>
        </div>
      </div>
    </DialogShell>
  )
}

/** Save Game dialog: emits action saveGame with description + saveMode (plan 4.4e). */
export function SaveDialog() {
  const open = useDialogs((s) => s.open)
  if (open !== 'save') return null
  return <SaveDialogBody />
}
