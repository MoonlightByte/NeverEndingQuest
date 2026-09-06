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
import { MapTab } from './MapTab'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'
import { InventoryViewProvider } from './InventoryViewState'

const TABS: ReadonlyArray<{ id: SheetTab; label: string }> = [
  { id: 'character', label: 'Character' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'spells', label: 'Spells & Magic' },
  { id: 'npcs', label: 'NPCs' },
]

export function RightPanelTabs() {
  const ember = useEmberDesktop()
  const [active, setActive] = useState<SheetTab>('character')

  useEffect(() => {
    requestTabData(active)
    const timer = window.setInterval(() => requestTabData(active), 5000)
    return () => window.clearInterval(timer)
  }, [active])

  return (
    <InventoryViewProvider>
    <div className="neq-rail-panel flex h-full min-h-0 flex-col overflow-hidden">
      <div role="tablist" aria-label="Party panel" className="neq-tabs flex h-10 shrink-0 bg-[#333]" onKeyDown={ember ? (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
        const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
        const index = tabs.indexOf(event.target as HTMLButtonElement)
        if (index < 0) return
        event.preventDefault()
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
        tabs[next]?.focus()
        tabs[next]?.click()
      } : undefined}>
        {(ember ? [...TABS, { id: 'map' as const, label: 'Map' }] : TABS).map((tab) => {
          const selected = active === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={ember ? 'ember-sheet-panel' : undefined}
              tabIndex={ember ? selected || (active === 'debug' && tab.id === 'character') ? 0 : -1 : undefined}
              onClick={() => setActive(tab.id)}
              className={
                'neq-tab-button flex-1 border-b-2 border-r border-card px-1 py-2 font-chrome text-xs font-bold transition-colors ' +
                (selected
                  ? 'border-accent bg-page text-accent'
                  : 'border-card text-secondary hover:text-primary')
              }
            >
              {tab.label}
            </button>
          )
        })}
        {!ember && <><button type="button" onClick={() => useDialogs.getState().openDialog('journal')} className="neq-tab-button flex-1 border-b-2 border-r border-card px-1 py-2 font-chrome text-xs font-bold text-secondary hover:text-primary">Journal</button>
        <button type="button" role="tab" aria-selected={active === 'debug'} onClick={() => setActive('debug')} className={'neq-tab-button flex-1 border-b-2 border-r border-card px-1 py-2 font-chrome text-xs font-bold ' + (active === 'debug' ? 'border-accent bg-panel text-accent' : 'border-card text-secondary hover:text-primary')}>Debug</button>
        <button type="button" role="tab" aria-selected={active === 'map'} onClick={() => setActive('map')} className={'neq-tab-button flex-1 border-b-2 px-1 py-2 font-chrome text-xs font-bold ' + (active === 'map' ? 'border-accent bg-panel text-accent' : 'border-card text-secondary hover:text-primary')}>Map</button>
        </>}
      </div>
      <div role="tabpanel" id={ember ? 'ember-sheet-panel' : undefined} aria-label={ember ? active : undefined} className="min-h-0 flex-1 overflow-hidden">
        {active === 'character' && <CharacterSheet />}
        {active === 'inventory' && <InventoryTab />}
        {active === 'spells' && <SpellsTab />}
        {active === 'npcs' && <NpcsTab />}
        {active === 'debug' && <DebugTab />}
        {active === 'map' && <MapTab />}
      </div>
      {ember && <div className="ember-sheet-footer">
        <button type="button" aria-pressed={active === 'debug'} onClick={() => setActive('debug')}><EmberIcon name="bug" />Debug</button>
        <button type="button" onClick={() => useDialogs.getState().openDialog('journal')}><EmberIcon name="book" />Journal</button>
      </div>}
    </div>
    </InventoryViewProvider>
  )
}
