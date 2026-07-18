import { useState } from 'react'
import { usePlayer } from '../../stores'
import { NpcDetailModal, type NpcModalKind } from './NpcDetailModal'
import {
  ABILITIES,
  abilityModifier,
  abilityScores,
  capitalizeWords,
  currencyOf,
  formatModifier,
  hpPercent,
  num,
  rec,
  str,
} from './characterData'

interface Selection {
  npc: Record<string, unknown>
  kind: NpcModalKind
}

export function NpcsTab() {
  const npcs = usePlayer((state) => state.npcs)
  const error = usePlayer((state) => state.dataErrors.npcs)
  const [selected, setSelected] = useState<Selection | null>(null)

  if (error) return <p className="p-4 font-body text-sm text-red-400">{error}</p>

  return (
    <div className="neq-npcs-content h-full overflow-y-auto">
      {npcs.length === 0 ? (
        <p className="text-sm italic text-secondary">No NPC data available</p>
      ) : npcs.map((npc, index) => {
        const name = str(npc['name'], 'Unknown NPC')
        const hp = num(npc['hitPoints'])
        const maxHp = num(npc['maxHitPoints'])
        const scores = abilityScores(npc)
        const currency = currencyOf(npc)
        const status = str(npc['status'], 'alive')
        // Legacy compares the raw value with the string "none"; an absent
        // field is therefore displayed literally as undefined.
        const condition = npc['condition'] === undefined ? 'undefined' : str(npc['condition'], 'none')
        const actions: Array<{ kind: NpcModalKind; label: string; visible: boolean }> = [
          { kind: 'saves', label: 'Saving Throw', visible: Array.isArray(npc['savingThrows']) && npc['savingThrows'].length > 0 },
          { kind: 'skills', label: 'Skills', visible: npc['skills'] !== undefined },
          { kind: 'inventory', label: 'Inventory', visible: Array.isArray(npc['equipment']) && npc['equipment'].length > 0 },
          { kind: 'features', label: 'Key Abilities', visible: Array.isArray(npc['classFeatures']) && npc['classFeatures'].length > 0 },
          { kind: 'traits', label: 'Racial Traits', visible: Array.isArray(npc['racialTraits']) && npc['racialTraits'].length > 0 },
          { kind: 'background', label: 'Background', visible: Boolean(rec(npc['backgroundFeature'])?.['name']) },
          { kind: 'spells', label: 'Spells', visible: Boolean(rec(npc['spellcasting']) && Object.keys(rec(npc['spellcasting'])!).length > 0) },
        ]
        const hpRatio = hpPercent(hp, maxHp)
        const hpClass = hpRatio > 75 ? 'healthy' : hpRatio > 50 ? 'injured' : hpRatio > 25 ? 'bloodied' : 'critical'
        return (
          <section key={`${name}-${index}`} className="neq-npc-character-sheet">
            <div className="neq-npc-header">
              <div className="neq-npc-header-main">
                <h3 className="neq-npc-name">{name}</h3>
                <p className="neq-npc-details">{`${str(npc['race'])} ${str(npc['class'])} • Level ${num(npc['level'], 1)} • ${capitalizeWords(str(npc['alignment']))}`}</p>
              </div>
              {npc['experience_points'] !== undefined && npc['exp_required_for_next_level'] !== undefined && <div className="neq-npc-header-xp"><div className="neq-xp-label">XP</div><div className="neq-xp-value">{`${num(npc['experience_points'])} / ${num(npc['exp_required_for_next_level'])}`}</div></div>}
              {npc['currency'] !== undefined && <div className="neq-npc-header-currency"><div className="neq-npc-currency-grid">{([['GP', currency.gold], ['SP', currency.silver], ['CP', currency.copper]] as const).map(([label, value]) => <div key={label} className="neq-npc-currency-item"><span className="neq-npc-currency-amount">{value}</span><span className="neq-npc-currency-type">{label}</span></div>)}</div></div>}
            </div>
            {npc['abilities'] !== undefined && <div className="neq-npc-abilities">
              <div className="neq-npc-ability-score neq-npc-combat-stat"><div className="neq-npc-ability-name">HP</div><div className="neq-npc-ability-value">{`${hp}/${maxHp}`}</div><div className="neq-npc-hp-bar"><div className={`neq-npc-hp-fill ${hpClass}`} style={{ width: `${hpRatio}%` }} /></div></div>
              <div className="neq-npc-ability-score neq-npc-combat-stat neq-npc-no-circle"><div className="neq-npc-ability-name">AC</div><div className="neq-npc-ability-value">{num(npc['armorClass'], 10)}</div></div>
              <div className="neq-npc-ability-score neq-npc-combat-stat neq-npc-no-circle"><div className="neq-npc-ability-name">INIT</div><div className="neq-npc-ability-value">{formatModifier(num(npc['initiative']))}</div></div>
              {ABILITIES.map((ability) => <div key={ability} className="neq-npc-ability-score"><div className="neq-npc-ability-name">{ability.slice(0, 3).toUpperCase()}</div><div className="neq-npc-ability-value">{scores[ability]}</div><div className="neq-npc-ability-modifier">{formatModifier(abilityModifier(scores[ability]))}</div></div>)}
            </div>}
            <div className="neq-npc-detail-buttons">
              {actions.filter((action) => action.visible).map((action) => <button key={action.kind} type="button" className="neq-npc-detail-button" onClick={() => setSelected({ npc, kind: action.kind })}>{action.label}</button>)}
              <button type="button" disabled aria-hidden="true" className="neq-npc-detail-button neq-npc-detail-spacer" />
            </div>
            {(status !== 'alive' || condition !== 'none') && <div className="neq-npc-status"><div className="neq-npc-status-item">Status: <span className={`neq-npc-status-value ${status}`}>{status}</span></div>{condition !== 'none' && <div className="neq-npc-status-item">Condition: <span className="neq-npc-condition-value">{condition}</span></div>}</div>}
          </section>
        )
      })}
      {selected && <NpcDetailModal npc={selected.npc} kind={selected.kind} onClose={() => setSelected(null)} />}
    </div>
  )
}
