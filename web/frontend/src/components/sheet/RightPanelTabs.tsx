/**
 * Right panel tab rail (plan Task 4.4d): Character / Inventory / Spells /
 * NPCs / Debug. Activating a tab emits its backing data request through the
 * frozen contract; components render purely from the Zustand stores.
 */
import { useEffect, useState } from 'react'
import { useDialogs } from '../../stores'
import { requestTabData, type SheetTab } from './sheetRequests'
import { CharacterSheet } from './CharacterSheet'
import { InventoryTab } from './InventoryTab'
import { SpellsTab } from './SpellsTab'
import { NpcsTab } from './NpcsTab'
import { DebugTab } from './DebugTab'

const TABS: ReadonlyArray<{ id: SheetTab; label: string }> = [
  { id: 'character', label: 'Character' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'spells', label: 'Spells & Magic' },
  { id: 'npcs', label: 'NPCs' },
]

export function RightPanelTabs() {
  const [active, setActive] = useState<SheetTab>('character')

  useEffect(() => {
    requestTabData(active)
    const timer = window.setInterval(() => requestTabData(active), 5000)
    return () => window.clearInterval(timer)
  }, [active])

  return (
    <div className="neq-rail-panel flex h-full min-h-0 flex-col overflow-hidden">
      <div role="tablist" aria-label="Party panel" className="flex h-10 shrink-0 bg-[#333]">
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
                'flex-1 border-b-2 border-r border-card px-1 py-2 font-chrome text-xs font-bold transition-colors ' +
                (selected
                  ? 'border-accent bg-page text-accent'
                  : 'border-card text-secondary hover:text-primary')
              }
            >
              {tab.label}
            </button>
          )
        })}
        <button type="button" onClick={() => useDialogs.getState().openDialog('journal')} className="flex-1 border-b-2 border-r border-card px-1 py-2 font-chrome text-xs font-bold text-secondary hover:text-primary">Journal</button>
        <button type="button" role="tab" aria-selected={active === 'debug'} onClick={() => setActive('debug')} className={'flex-1 border-b-2 px-1 py-2 font-chrome text-xs font-bold ' + (active === 'debug' ? 'border-accent bg-panel text-accent' : 'border-card text-secondary hover:text-primary')}>Debug</button>
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
