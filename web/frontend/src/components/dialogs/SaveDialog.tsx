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
    <DialogShell title="Save Game" onClose={closeDialog} maxWidth="600px" legacy>
      <div className="font-chrome text-sm leading-[normal]">
        <div className="mb-5">
          <label htmlFor="save-description" className="mb-[5px] block text-primary">
            Description (optional):
          </label>
          <textarea
            id="save-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter a brief description of your current progress..."
            rows={2}
            className="mb-[10px] min-h-[60px] w-full resize-y rounded border border-[#555] bg-[#333] p-2 font-chrome text-sm text-primary outline-none focus:border-accent"
          />

          <label htmlFor="save-mode" className="mb-[5px] block text-primary">
            Save Type:
          </label>
          <div className="mt-[10px]">
            <select
              id="save-mode"
              value={saveMode}
              onChange={(e) => setSaveMode(e.target.value as SaveMode)}
              className="mb-[10px] w-full rounded border border-[#555] bg-[#333] p-2 font-chrome text-sm text-primary outline-none focus:border-accent"
            >
              <option value="essential">Game State - Complete Save (Recommended)</option>
              <option value="full">Archive Edition - Includes Historical Data</option>
            </select>

            <div className="mt-[19px] h-[256px] rounded-md border border-card bg-page p-[15px]">
              <div className="mb-3 flex items-center gap-2 text-base">
                <span className="text-lg">{saveMode === 'essential' ? '💾' : '📚'}</span>
                <strong className="text-primary">{info.title}</strong>
                <span className="ml-auto rounded-xl bg-[#4caf50] px-2 py-0.5 text-[10px] font-bold tracking-[.5px] text-white">
                  {info.badge}
                </span>
              </div>
              <p className="text-primary">{saveMode === 'essential' ? 'Complete game restoration with all essential data:' : 'Everything from Game State Save plus:'}</p>
              <ul className="my-[10px] list-none p-0 text-primary">
                {info.includes.map((line) => (
                  <li key={line} className="py-1">{saveMode === 'essential' ? '✅' : '📜'} {line}</li>
                ))}
              </ul>
              <p className="mt-3 rounded border-l-4 border-accent bg-[#2d4a2d] px-3 py-2 text-xs italic text-[#c8e6c9]">{info.note}</p>
            </div>
          </div>
        </div>

        <div className="mt-[39px] flex justify-between gap-[10px]">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button type="button" aria-label="Save Game" className={dialogButtonPrimary} onClick={performSave}>
            <span className="mr-1.5">💾</span> Save Game
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
