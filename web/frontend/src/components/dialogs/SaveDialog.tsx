import { useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs } from '../../stores'
import { DialogShell, dialogButtonPrimary, dialogButtonSecondary } from './DialogShell'
import { useEmberViewport } from '../layout/useEmberViewport'
import { EmberIcon } from '../layout/EmberIcon'

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
      'Extended conversation archives',
      'Detailed combat logs and analysis',
      'Campaign transition summaries',
      'Multi-AI conversation tracking',
      'Historical data for review',
    ],
    note: 'Ideal for DMs, campaign analysis, or long-term archival. Larger file size.',
  },
}

/** Body unmounts when the dialog closes, so each open starts with a fresh form. */
function SaveDialogBody() {
  const ember = useEmberViewport()
  const [description, setDescription] = useState('')
  const [saveMode, setSaveMode] = useState<SaveMode>('essential')
  const descriptionRef = useRef<HTMLTextAreaElement>(null)
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
    <DialogShell title="Save Game" onClose={closeDialog} maxWidth="600px" legacy className="neq-enhanced-save-dialog-parity" initialFocusRef={descriptionRef}>
      <div>
        <div className="neq-save-form-parity">
          <label htmlFor="save-description">
            Description (optional):
          </label>
          <textarea
            ref={descriptionRef}
            id="save-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter a brief description of your current progress..."
            rows={2}
          />

          <label htmlFor="save-mode">
            Save Type:
          </label>
          <div className="neq-save-mode-container-parity">
            <select
              id="save-mode"
              value={saveMode}
              onChange={(e) => setSaveMode(e.target.value as SaveMode)}
            >
              <option value="essential">Game State - Complete Save (Recommended)</option>
              <option value="full">Archive Edition - Includes Historical Data</option>
            </select>

            <div className="neq-save-mode-info-parity">
              <div className="neq-save-mode-title-parity">
                <span className="neq-save-icon-parity" aria-hidden="true">{ember ? <EmberIcon name="book" /> : saveMode === 'essential' ? '💾' : '📚'}</span>
                <strong>{info.title}</strong>
                <span className={`neq-save-badge-parity ${saveMode}`}>
                  {info.badge}
                </span>
              </div>
              <div className="neq-save-description-parity">
                {saveMode === 'essential' ? 'Complete game restoration with all essential data:' : 'Everything from Game State Save plus:'}
                <ul>
                  {info.includes.map((line, index) => (
                    <li key={line}>{`${ember ? '•' : saveMode === 'essential' ? '✅' : ['📜', '⚔️', '🗃️', '🤖', '📊'][index]} ${line}`}</li>
                  ))}
                </ul>
                <div className="neq-save-note-parity">{info.note}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="neq-dialog-buttons-parity">
          <button type="button" className={dialogButtonSecondary} onClick={closeDialog}>
            Cancel
          </button>
          <button type="button" aria-label="Save Game" className={dialogButtonPrimary} onClick={performSave}>
            {!ember && <span className="neq-button-icon-parity">💾</span>} Save Game
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
