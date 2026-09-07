import type { ReactNode } from 'react'
import type { NpcModalKind } from './NpcDetailModal'
import { CharacterSheetIdentity } from './CharacterSheetIdentity'
import { ABILITIES, abilityModifier, abilityScores, capitalizeWords, formatModifier, hpPercent, num, saveRows, str } from './characterData'

/** Desktop presentation of the same full NPC record used by the legacy menus. */
export function NpcCharacterSheet({ npc, portrait, actions, onSelect, hideIdentity = false }: {
  npc: Record<string, unknown>
  portrait: ReactNode
  actions: Array<{ kind: NpcModalKind; label: string }>
  onSelect: (kind: NpcModalKind) => void
  hideIdentity?: boolean
}) {
  const scores = abilityScores(npc)
  const hp = num(npc['hitPoints'])
  const maxHp = num(npc['maxHitPoints'])
  const ratio = hpPercent(hp, maxHp)
  const status = str(npc['status'], 'alive')
  const condition = str(npc['condition']) || (Array.isArray(npc['conditions']) ? npc['conditions'].filter((value) => typeof value === 'string').join(', ') : '')
  const actionButton = (kind: NpcModalKind) => {
    const action = actions.find((item) => item.kind === kind)
    return action && <button key={kind} type="button" onClick={() => onSelect(kind)}>{action.label}<span aria-hidden="true">›</span></button>
  }
  return <section className={`tavern-character-sheet${hideIdentity ? ' tcs-body-only' : ''}`} aria-label={`${str(npc['name'])} character sheet`}>
    {!hideIdentity && <CharacterSheetIdentity stats={npc} portrait={portrait} />}
    {npc['abilities'] !== undefined && <section className="tcs-abilities" aria-label="Ability scores">
      <h4>Abilities</h4>
      {ABILITIES.map((ability) => <div className="tcs-ability" key={ability}>
        <span className="tcs-label">{capitalizeWords(ability)}</span>
        <strong aria-label={`${ability} modifier`}>{formatModifier(abilityModifier(scores[ability]))}</strong>
        <span className="tcs-score" aria-label={`${ability} score`}>{scores[ability]}</span>
      </div>)}
    </section>}
      {npc['abilities'] !== undefined && <section className="tcs-combat" aria-label="Combat statistics">
        <h4>Combat</h4>
        <div className="tcs-defense"><div className="tcs-ac"><span className="tcs-label">Armor class</span><strong>{num(npc['armorClass'], 10)}</strong></div>
          <div className="tcs-initiative"><span className="tcs-label">Initiative</span><strong>{formatModifier(num(npc['initiative']))}</strong></div></div>
        <div className="tcs-hp"><span className="tcs-label">Hit points</span><strong>{hp}<small> / {maxHp}</small></strong><div className="tcs-hp-track"><span data-low={ratio <= 50} style={{ width: `${ratio}%` }} /></div></div>
      </section>}
    <div className="tcs-mechanics">
      {(status !== 'alive' || (condition && condition !== 'none')) && <p className="tcs-condition">{[status !== 'alive' ? status : '', condition !== 'none' ? condition : ''].filter(Boolean).join(' · ')}</p>}
      {actions.some((action) => action.kind === 'saves' || action.kind === 'skills') && <section className="tcs-checks">
        <h4>Saving throws & skills</h4>
        {actions.some((action) => action.kind === 'saves') && <dl className="tcs-saves">{saveRows(npc).map((save) => <div key={save.name}><dt><span aria-label={save.proficient ? 'Proficient' : 'Not proficient'}>{save.proficient ? '●' : '○'}</span> {save.name.slice(0, 3).toUpperCase()}</dt><dd>{formatModifier(save.bonus)}</dd></div>)}</dl>}
        <div className="tcs-actions">{actionButton('saves')}{actionButton('skills')}</div>
      </section>}
      {actions.some((action) => action.kind === 'inventory' || action.kind === 'spells') && <section className="tcs-equipment"><h4>Equipment & magic</h4><div className="tcs-actions">{actionButton('inventory')}{actionButton('spells')}</div></section>}
      {actions.some((action) => ['features', 'traits', 'background'].includes(action.kind)) && <section className="tcs-features"><h4>Features & background</h4><div className="tcs-actions">{actionButton('features')}{actionButton('traits')}{actionButton('background')}</div></section>}
    </div>
    <div className="tcs-story">
      {(['personality_traits', 'ideals', 'bonds', 'flaws'] as const).some((key) => str(npc[key])) && <section className="tcs-biography"><h4>Personality & bonds</h4><dl>{(['personality_traits', 'ideals', 'bonds', 'flaws'] as const).map((key) => str(npc[key]) ? <div key={key}><dt>{capitalizeWords(key.replace(/_/g, ' '))}</dt><dd>{str(npc[key])}</dd></div> : null)}</dl></section>}
    </div>
  </section>
}
