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

// Text labels only -- no icons (binding design decision, plan Task 7). Seven
// tabs (Character/Inventory/Spells & Magic/NPCs/Journal/Debug/Map) need to
// shrink to fit the rail's 420px floor width rather than switching to icons.
// The Tailwind utilities on each button (px-0.5, text-[10px]) cover that
// shrink below the 761px breakpoint; above it, tokens.css's legacy-parity
// `.neq-tab-button` rule fixes a wider 6-tab-era padding/font-size, so the
// compact 7-tab values live in an unlayered override there
// (`.neq-tabs .neq-tab-button`, plan Task 7 fix round 1 F1) rather than as
// Tailwind classes, which a same-specificity unlayered rule would beat.
//
// Every button uses `flex-auto` (flex: 1 1 auto), not `flex-1` (flex: 1 1
// 0%): with a 0% basis, all 7 buttons grow to exactly equal widths
// regardless of how much text each holds, so "Spells & Magic" -- by far the
// longest label -- was clipped by `truncate` even though short labels like
// "Map" sat on wide unused padding. `flex-auto`'s content-sized basis gives
// each button room for its own label first and only then splits the
// remaining slack evenly, which fits all 7 labels untruncated at both the
// 420px and 520px rail widths (fix round 2 F1 residual; verified with a
// Playwright/Chromium measurement against the built CSS, see
// task-7-report.md). A same-specificity unlayered rule setting `flex` would
// still beat this the way F1 beat the old `text-[10px]`/`px-0.5`, but no
// such rule exists for `flex` in tokens.css's parity block, so the utility
// applies as authored.
//
// Journal/Debug/Map are hardcoded <button>s below, not TABS entries: Journal
// opens a dialog instead of switching `active`, and Debug/Map (unlike
// Journal) do participate in `active`/`aria-selected` but were kept as
// separate elements to match the pre-existing Debug pattern rather than
// partially folding only one of the two into the mapped array.
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
      <div role="tablist" aria-label="Party panel" className="neq-tabs flex h-10 shrink-0 bg-[#333]">
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
                'neq-tab-button flex-auto truncate border-b-2 border-r border-card px-0.5 py-2 font-chrome text-[10px] font-bold transition-colors ' +
                (selected
                  ? 'border-accent bg-page text-accent'
                  : 'border-card text-secondary hover:text-primary')
              }
            >
              {tab.label}
            </button>
          )
        })}
        <button type="button" onClick={() => useDialogs.getState().openDialog('journal')} className="neq-tab-button flex-auto truncate border-b-2 border-r border-card px-0.5 py-2 font-chrome text-[10px] font-bold text-secondary hover:text-primary">Journal</button>
        <button type="button" role="tab" aria-selected={active === 'debug'} onClick={() => setActive('debug')} className={'neq-tab-button flex-auto truncate border-b-2 border-r border-card px-0.5 py-2 font-chrome text-[10px] font-bold ' + (active === 'debug' ? 'border-accent bg-panel text-accent' : 'border-card text-secondary hover:text-primary')}>Debug</button>
        <button type="button" role="tab" aria-selected={active === 'map'} onClick={() => setActive('map')} className={'neq-tab-button flex-auto truncate border-b-2 px-0.5 py-2 font-chrome text-[10px] font-bold ' + (active === 'map' ? 'border-accent bg-panel text-accent' : 'border-card text-secondary hover:text-primary')}>Map</button>
      </div>
      <div role="tabpanel" className="min-h-0 flex-1 overflow-hidden">
        {active === 'character' && <CharacterSheet />}
        {active === 'inventory' && <InventoryTab />}
        {active === 'spells' && <SpellsTab />}
        {active === 'npcs' && <NpcsTab />}
        {active === 'debug' && <DebugTab />}
        {active === 'map' && <MapTab />}
      </div>
    </div>
  )
}
