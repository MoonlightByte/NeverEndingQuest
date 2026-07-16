/**
 * NPC detail modal (plan Task 4.4d): tabbed Saves / Skills / Spells /
 * Inventory. Activating a tab emits the matching request_npc_* contract
 * event; the body renders npc_details_response (raw NPC character file,
 * keyed by modalType) and npc_inventory_response (equipment array) from the
 * player store. View derivations ported from the legacy showNPC* renderers.
 */
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { usePlayer } from '../../stores'
import { requestNpcTabData, type NpcDetailTab } from './sheetRequests'
import {
  equipmentFromArray,
  formatModifier,
  saveRows,
  skillRows,
  slotTone,
  spellcastingView,
} from './characterData'

const NPC_TABS: ReadonlyArray<{ id: NpcDetailTab; label: string }> = [
  { id: 'saves', label: 'Saves' },
  { id: 'skills', label: 'Skills' },
  { id: 'spells', label: 'Spells' },
  { id: 'inventory', label: 'Inventory' },
]

// ASCII-only source: proficiency dots as escapes (filled / open circle).
const PROFICIENT_DOT = '\u25CF'
const UNPROFICIENT_DOT = '\u25CB'

const TONE_COLOR: Record<'available' | 'low' | 'exhausted', string> = {
  available: 'var(--accent)',
  low: '#e67e22',
  exhausted: '#e74c3c',
}

function Loading() {
  return <p className="p-3 text-sm text-secondary">Loading...</p>
}

function ErrorText({ message }: { message: string }) {
  return <p className="p-3 text-sm text-red-400">{message}</p>
}

function SavesBody({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="p-3">
      {saveRows(data).map((save) => (
        <div
          key={save.name}
          className="flex justify-between border-b border-card/60 py-1 text-sm last:border-b-0"
        >
          <span className={save.proficient ? 'text-primary' : 'text-secondary'}>
            {save.name} {save.proficient ? PROFICIENT_DOT : UNPROFICIENT_DOT}
          </span>
          <span className="text-accent">{formatModifier(save.bonus)}</span>
        </div>
      ))}
    </div>
  )
}

function SkillsBody({ data }: { data: Record<string, unknown> }) {
  const rows = skillRows(data)
  if (rows.length === 0) {
    return <p className="p-3 text-sm italic text-secondary">No skills available.</p>
  }
  return (
    <div className="p-3">
      {rows.map((skill) => (
        <div
          key={skill.name}
          className="flex justify-between border-b border-card/60 py-1 text-sm last:border-b-0"
        >
          <span className="text-primary">{skill.name}</span>
          <span className="text-accent">{formatModifier(skill.bonus)}</span>
        </div>
      ))}
    </div>
  )
}

function SpellsBody({ data }: { data: Record<string, unknown> }) {
  const view = spellcastingView(data)
  if (!view) {
    return <p className="p-3 text-sm italic text-secondary">No spells available.</p>
  }
  return (
    <div className="p-3">
      {(view.saveDC !== null || view.attackBonus !== null) && (
        <div className="flex gap-4 font-chrome text-xs text-secondary">
          {view.saveDC !== null && (
            <span>
              Save DC: <span className="text-primary">{view.saveDC}</span>
            </span>
          )}
          {view.attackBonus !== null && (
            <span>
              Attack: <span className="text-primary">{formatModifier(view.attackBonus)}</span>
            </span>
          )}
        </div>
      )}
      {view.levels.map((group) => (
        <div key={group.levelIndex} className="mt-2">
          <div className="flex items-baseline justify-between">
            <span className="font-display text-xs text-accent">{group.levelName}</span>
            {group.slots && (
              <span
                className="font-chrome text-[10px]"
                style={{ color: TONE_COLOR[slotTone(group.slots)] }}
              >
                {group.slots.current}/{group.slots.max} slots
              </span>
            )}
          </div>
          {group.spells.map((spell) => (
            <div key={spell} className="border-b border-card/60 py-0.5 text-sm text-primary last:border-b-0">
              {spell}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function InventoryBody({ items }: { items: unknown[] }) {
  const equipment = equipmentFromArray(items)
  if (equipment.length === 0) {
    return <p className="p-3 text-sm italic text-secondary">No items in inventory.</p>
  }
  return (
    <div className="p-3">
      {equipment.map((item, i) => (
        <div key={`${item.name}-${i}`} className="border-b border-card/60 py-1 last:border-b-0">
          <div className="flex justify-between text-sm">
            <span className="text-primary">{item.name}</span>
            <span className="text-secondary">x{item.quantity}</span>
          </div>
          <div className="font-chrome text-xs text-secondary">{item.type}</div>
          {item.description !== '' && (
            <div className="mt-0.5 text-xs text-secondary">{item.description}</div>
          )}
        </div>
      ))}
    </div>
  )
}

export function NpcDetailModal({ npcName, onClose }: { npcName: string; onClose: () => void }) {
  const [tab, setTab] = useState<NpcDetailTab>('saves')
  const npcDetails = usePlayer((s) => s.npcDetails)
  const npcInventory = usePlayer((s) => s.npcInventory)

  // Request the active tab's data whenever the tab or subject changes.
  useEffect(() => {
    requestNpcTabData(tab, npcName)
  }, [tab, npcName])

  // Drop stale modal payloads when the modal unmounts.
  useEffect(() => () => usePlayer.getState().clearNpcModal(), [])

  const details =
    npcDetails && npcDetails.npcName === npcName && npcDetails.modalType === tab
      ? npcDetails
      : null
  const inventory = npcInventory && npcInventory.npcName === npcName ? npcInventory : null

  let body: ReactNode
  if (tab === 'inventory') {
    if (inventory?.error) body = <ErrorText message={inventory.error} />
    else if (!inventory || inventory.data === null) body = <Loading />
    else body = <InventoryBody items={inventory.data} />
  } else if (details?.error) {
    body = <ErrorText message={details.error} />
  } else if (!details || details.data === null) {
    body = <Loading />
  } else if (tab === 'saves') {
    body = <SavesBody data={details.data} />
  } else if (tab === 'skills') {
    body = <SkillsBody data={details.data} />
  } else {
    body = <SpellsBody data={details.data} />
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${npcName} details`}
        onClick={(e) => e.stopPropagation()}
        className="neq-card flex max-h-[80vh] w-full max-w-md flex-col overflow-hidden font-body"
      >
        <div className="flex shrink-0 items-center justify-between border-b-2 border-card px-3 py-2">
          <h3 className="font-display text-base text-accent">{npcName}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded border-2 border-card px-2 font-chrome text-sm text-secondary hover:border-accent hover:text-primary"
          >
            X
          </button>
        </div>
        <div role="tablist" aria-label="NPC details" className="flex shrink-0">
          {NPC_TABS.map((t) => {
            const selected = tab === t.id
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setTab(t.id)}
                className={
                  'flex-1 border-b-2 px-1 py-1.5 font-display text-xs transition-colors ' +
                  (selected
                    ? 'border-accent bg-page text-accent'
                    : 'border-card text-secondary hover:text-primary')
                }
              >
                {t.label}
              </button>
            )
          })}
        </div>
        <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto">
          {body}
        </div>
      </div>
    </div>
  )
}
