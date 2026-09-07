import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { CharacterSheetIdentity } from './CharacterSheetIdentity'
import { CharacterSheetTabs, type CharacterSheetTab } from './CharacterSheetTabs'
import { NpcCharacterSheet } from './NpcCharacterSheet'
import { NpcDetailContent, type NpcModalKind } from './NpcDetailModal'
import { NpcInventoryPanel } from './NpcInventoryPanel'

/** Keep the full NPC identity mounted while navigating its live character data. */
export function NpcTabbedSheet({ npc, portrait, actions, onSelect }: {
  npc: Record<string, unknown>
  portrait: ReactNode
  actions: Array<{ kind: NpcModalKind; label: string }>
  onSelect: (kind: NpcModalKind) => void
}) {
  const [active, setActive] = useState<CharacterSheetTab>('character')
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => { if (panel.current) panel.current.scrollTop = 0 }, [active])
  return <div className="tcs-tabbed-shell">
    <CharacterSheetIdentity stats={npc} portrait={portrait} />
    <CharacterSheetTabs id={id} active={active} onChange={setActive} label="NPC character" />
    <div ref={panel} className="tps-panel" role="tabpanel" tabIndex={0} id={`${id}-panel`} aria-labelledby={`${id}-${active}`}>
      {active === 'character'
        ? <NpcCharacterSheet npc={npc} hideIdentity portrait={null} actions={actions.filter(action => action.kind !== 'inventory' && action.kind !== 'spells')} onSelect={onSelect} />
        : active === 'inventory' ? <NpcInventoryPanel npc={npc} /> : <NpcDetailContent npc={npc} kind={active} />}
    </div>
  </div>
}
