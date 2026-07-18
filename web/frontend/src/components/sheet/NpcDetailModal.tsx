import type { ReactNode } from 'react'
import {
  arr,
  equipmentList,
  formatModifier,
  rec,
  saveRows,
  skillRows,
  slotTone,
  spellcastingView,
  str,
} from './characterData'

export type NpcModalKind =
  | 'saves'
  | 'skills'
  | 'inventory'
  | 'features'
  | 'traits'
  | 'background'
  | 'spells'

const TITLES: Record<NpcModalKind, string> = {
  saves: 'Saving Throws',
  skills: 'Skills',
  inventory: 'Inventory',
  features: 'Key Abilities',
  traits: 'Racial Traits',
  background: 'Background',
  spells: 'Spells',
}

function Empty({ children }: { children: string }) {
  return <p className="p-3 text-sm italic text-secondary">{children}</p>
}

function Row({ name, detail, showDetail = false }: { name: string; detail?: ReactNode; showDetail?: boolean }) {
  return (
    <div className="mb-1 rounded bg-[#1a1a1a] px-2 py-1.5 text-sm">
      <div className="font-bold text-primary">{name}</div>
      {showDetail && detail !== undefined && detail !== '' && (
        <div className="mt-0.5 text-xs text-secondary">{detail}</div>
      )}
    </div>
  )
}

function ListBody({ raw, empty }: { raw: unknown; empty: string }) {
  const entries = arr(raw).map(rec).filter((item): item is Record<string, unknown> => item !== null)
  if (entries.length === 0) return <Empty>{empty}</Empty>
  return (
    <div>
      {entries.map((item, index) => (
        <Row
          key={`${str(item['name'], 'Item')}-${index}`}
          name={str(item['name'], 'Unknown')}
          detail={str(item['description'], str(item['detail']))}
        />
      ))}
    </div>
  )
}

function ModalBody({ npc, kind }: { npc: Record<string, unknown>; kind: NpcModalKind }) {
  if (kind === 'saves') {
    return (
      <div>
        {saveRows(npc).map((save) => (
          <div key={save.name} className="flex justify-between border-b border-card/60 py-1 text-sm">
            <span className={save.proficient ? 'text-primary' : 'text-secondary'}>
              {save.name} {save.proficient ? '\u25CF' : '\u25CB'}
            </span>
            <span className="text-accent">{formatModifier(save.bonus)}</span>
          </div>
        ))}
      </div>
    )
  }
  if (kind === 'skills') {
    const skills = skillRows(npc)
    if (skills.length === 0) return <Empty>No skills available.</Empty>
    return (
      <div>
        {skills.map((skill) => (
          <div key={skill.name} className="flex justify-between border-b border-card/60 py-1 text-sm">
            <span className="text-primary">{skill.name}</span>
            <span className="text-accent">{formatModifier(skill.bonus)}</span>
          </div>
        ))}
      </div>
    )
  }
  if (kind === 'inventory') {
    const items = equipmentList(npc)
    if (items.length === 0) return <Empty>No items in inventory.</Empty>
    return (
      <div>
        {items.map((item, index) => (
          <div key={`${item.name}-${index}`} className="mb-2 rounded-[5px] border-l-[3px] border-accent bg-page p-2">
            <div className="mb-1 flex items-center justify-between">
              <div className="text-[14px] font-bold leading-[normal] text-primary">{item.name}</div>
              <div className="rounded bg-[#333] px-1.5 py-0.5 text-[12px] leading-[normal] text-accent">x{item.quantity}</div>
            </div>
            <div className="mt-1 text-xs text-secondary">{item.type}</div>
            {item.description && <div className="mt-0.5 text-[11px] italic text-[#ccc]">{item.description}</div>}
          </div>
        ))}
      </div>
    )
  }
  if (kind === 'features') return <ListBody raw={npc['classFeatures']} empty="No key abilities." />
  if (kind === 'traits') return <ListBody raw={npc['racialTraits']} empty="No racial traits." />
  if (kind === 'background') {
    const feature = rec(npc['backgroundFeature'])
    return feature ? (
      <div>
        <Row name={str(feature['name'], 'Background')} detail={str(feature['description'])} />
      </div>
    ) : <Empty>No background feature.</Empty>
  }

  const casting = spellcastingView(npc)
  if (!casting) return <Empty>No spells available.</Empty>
  return (
    <div>
      <div className="flex gap-4 text-xs text-secondary">
        {casting.saveDC !== null && <span>Save DC: <b className="text-primary">{casting.saveDC}</b></span>}
        {casting.attackBonus !== null && <span>Attack: <b className="text-primary">{formatModifier(casting.attackBonus)}</b></span>}
      </div>
      {casting.levels.map((level) => (
        <div key={level.levelIndex} className="mt-3">
          <div className="flex justify-between font-display text-xs text-accent">
            <span>{level.levelName}</span>
            {level.slots && <span data-tone={slotTone(level.slots)}>{level.slots.current}/{level.slots.max} slots</span>}
          </div>
          {level.spells.map((spell) => <Row key={spell} name={spell} />)}
        </div>
      ))}
    </div>
  )
}

export function NpcDetailModal({
  npc,
  kind,
  onClose,
}: {
  npc: Record<string, unknown>
  kind: NpcModalKind
  onClose: () => void
}) {
  const name = str(npc['name'], 'Unknown NPC')
  const inventoryStyle = kind === 'inventory' || kind === 'spells'
  const title = `${name}'s ${kind === 'spells' ? 'Spellcasting' : TITLES[kind]}`
  return (
    <div className="fixed inset-0 z-40 bg-black/70" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="mx-auto flex w-[80%] flex-col overflow-hidden rounded-lg border-2 border-[#4caf50] bg-[#2c2c2c] p-5 font-chrome leading-[normal]"
        style={{ marginTop: inventoryStyle ? '5%' : '10%', maxWidth: inventoryStyle ? '600px' : '500px', maxHeight: inventoryStyle ? '80%' : '70%' }}
      >
        <div className="mb-[15px] flex items-center justify-between border-b-2 border-card pb-[10px]">
          <h3 className={inventoryStyle ? 'text-xl font-bold text-accent' : 'text-[18px] font-bold text-accent'}>{title}</h3>
          <button type="button" onClick={onClose} aria-label="Close" className="border-0 bg-transparent text-2xl font-bold leading-none text-[#aaa] hover:text-white">&times;</button>
        </div>
        <div className="min-h-0 max-h-[300px] flex-1 overflow-y-auto"><ModalBody npc={npc} kind={kind} /></div>
      </div>
    </div>
  )
}
