/**
 * Right panel tab rail (plan Task 4.4d): Character / Inventory / Spells /
 * NPCs / Debug. Activating a tab emits its backing data request through the
 * frozen contract; components render purely from the Zustand stores.
 */
import { useEffect, useState } from 'react'
import { requestTabData, type SheetTab } from './sheetRequests'
import { CharacterSheet } from './CharacterSheet'
import { InventoryTab } from './InventoryTab'
import { SpellsTab } from './SpellsTab'
import { NpcsTab } from './NpcsTab'
import { DebugTab } from './DebugTab'

const TABS: ReadonlyArray<{ id: SheetTab; label: string }> = [
  { id: 'character', label: 'Character' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'spells', label: 'Spells' },
  { id: 'npcs', label: 'NPCs' },
  { id: 'debug', label: 'Debug' },
]

export function RightPanelTabs() {
  const [active, setActive] = useState<SheetTab>('character')

  useEffect(() => {
    requestTabData(active)
  }, [active])

  return (
    <div className="neq-card flex h-full min-h-0 flex-col overflow-hidden">
      <div role="tablist" aria-label="Party panel" className="flex shrink-0">
        {TABS.map((tab) => {
          const selected = active === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setActive(tab.id)}
              className={
                'flex-1 border-b-2 px-1 py-2 font-display text-xs tracking-wide transition-colors ' +
                (selected
                  ? 'border-accent bg-page text-accent'
                  : 'border-card text-secondary hover:text-primary')
              }
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" className="min-h-0 flex-1 overflow-hidden">
        {active === 'character' && <CharacterSheet />}
        {active === 'inventory' && <InventoryTab />}
        {active === 'spells' && <SpellsTab />}
        {active === 'npcs' && <NpcsTab />}
        {active === 'debug' && <DebugTab />}
      </div>
    </div>
  )
}
