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
  spells: 'Spellcasting',
}

function DetailItem({ name, bonus, title }: { name: string; bonus?: string; title?: string }) {
  return <div className="neq-npc-details-item" title={title}><span className="neq-npc-details-name">{name}</span>{bonus !== undefined && <span className="neq-npc-details-bonus">{bonus}</span>}</div>
}

function DetailBody({ npc, kind }: { npc: Record<string, unknown>; kind: Exclude<NpcModalKind, 'inventory' | 'spells'> }) {
  if (kind === 'saves') return <>{saveRows(npc).map((save) => <DetailItem key={save.name} name={`${save.name} ${save.proficient ? '●' : '○'}`} bonus={formatModifier(save.bonus)} />)}</>
  if (kind === 'skills') {
    const skills = skillRows(npc)
    return <>{skills.length ? skills.map((skill) => <DetailItem key={skill.name} name={skill.name} bonus={formatModifier(skill.bonus)} />) : <div className="neq-npc-details-item">No skills available.</div>}</>
  }
  const raw = kind === 'features' ? npc['classFeatures'] : kind === 'traits' ? npc['racialTraits'] : rec(npc['backgroundFeature']) ? [npc['backgroundFeature']] : []
  const items = arr(raw).map(rec).filter((item): item is Record<string, unknown> => item !== null)
  const emptyName = kind === 'features' ? 'key abilities' : kind === 'traits' ? 'racial traits' : 'background'
  return <>{items.length ? items.map((item, index) => <DetailItem key={`${str(item['name'])}-${index}`} name={str(item['name'])} title={str(item['description'], str(item['detail'])) || undefined} />) : <div className="neq-npc-details-item">No {emptyName} available.</div>}</>
}

function InventoryBody({ npc }: { npc: Record<string, unknown> }) {
  const items = equipmentList(npc)
  if (!items.length) return <div className="neq-npc-inventory-item">No items in inventory.</div>
  return <>{items.map((item, index) => <div key={`${item.name}-${index}`} className="neq-npc-inventory-item"><div className="neq-npc-inventory-item-header"><div className="neq-npc-inventory-item-name">{item.name}</div><div className="neq-npc-inventory-item-quantity">x{item.quantity || 1}</div></div><div className="neq-npc-inventory-item-details">{item.type}</div>{item.description && <div className="neq-npc-inventory-item-description">{item.description}</div>}</div>)}</>
}

function SpellsBody({ npc }: { npc: Record<string, unknown> }) {
  const casting = spellcastingView(npc)
  if (!casting) return <div className="neq-npc-no-spellcasting">This character does not have spellcasting abilities.</div>
  return <div className="neq-npc-modal-spellcasting">
    {(casting.saveDC !== null || casting.attackBonus !== null) && <div className="neq-npc-modal-spell-stats">{casting.saveDC !== null && <span>Save DC: {casting.saveDC}</span>}{casting.attackBonus !== null && <span>Spell Attack: {formatModifier(casting.attackBonus)}</span>}</div>}
    {casting.levels.map((level) => <div key={level.levelIndex} className="neq-npc-modal-spell-level"><div className="neq-npc-modal-spell-header"><span className="neq-npc-modal-spell-name">{level.levelName}</span>{level.slots && <span className={`neq-npc-modal-spell-slots ${slotTone(level.slots)}`}>{level.slots.current}/{level.slots.max} slots</span>}</div><div className="neq-npc-modal-spell-list">{level.spells.map((spell) => <div key={spell} className="neq-npc-modal-spell-item"><span>{spell}</span></div>)}</div></div>)}
  </div>
}

export function NpcDetailModal({ npc, kind, onClose }: { npc: Record<string, unknown>; kind: NpcModalKind; onClose: () => void }) {
  const name = str(npc['name'], 'Unknown NPC')
  const title = `${name}'s ${TITLES[kind]}`
  const expanded = kind === 'inventory' || kind === 'spells'
  return <div className={expanded ? 'neq-npc-inventory-modal' : 'neq-npc-details-modal'} onClick={onClose}>
    <div role="dialog" aria-modal="true" aria-label={title} className={expanded ? 'neq-npc-inventory-modal-content' : 'neq-npc-details-modal-content'} onClick={(event) => event.stopPropagation()}>
      <div className={expanded ? 'neq-npc-inventory-header' : 'neq-npc-details-header'}><div className={expanded ? 'neq-npc-inventory-title' : 'neq-npc-details-title'}>{title}</div><span role="button" tabIndex={0} aria-label="Close" className={expanded ? 'neq-npc-inventory-close' : 'neq-npc-details-close'} onClick={onClose} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') onClose() }}>&times;</span></div>
      <div className={expanded ? 'neq-npc-inventory-body' : 'neq-npc-details-body'}>{kind === 'inventory' ? <InventoryBody npc={npc} /> : kind === 'spells' ? <SpellsBody npc={npc} /> : <DetailBody npc={npc} kind={kind} />}</div>
    </div>
  </div>
}
