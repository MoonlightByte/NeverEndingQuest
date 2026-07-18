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
  hpTone,
  num,
  rec,
  str,
} from './characterData'

interface Selection {
  npc: Record<string, unknown>
  kind: NpcModalKind
}

const buttonClass = 'rounded border border-card bg-panel px-2 py-1 text-xs text-primary hover:border-accent'

export function NpcsTab() {
  const npcs = usePlayer((state) => state.npcs)
  const error = usePlayer((state) => state.dataErrors.npcs)
  const [selected, setSelected] = useState<Selection | null>(null)

  if (error) return <p className="p-4 font-body text-sm text-red-400">{error}</p>

  return (
    <div className="h-full overflow-y-auto p-3 font-body">
      {npcs.length === 0 ? (
        <p className="text-sm italic text-secondary">No NPC data available</p>
      ) : npcs.map((npc, index) => {
        const name = str(npc['name'], 'Unknown NPC')
        const hp = num(npc['hitPoints'])
        const maxHp = num(npc['maxHitPoints'])
        const tone = hpTone(hp, maxHp)
        const scores = abilityScores(npc)
        const currency = currencyOf(npc)
        const status = str(npc['status'], 'alive')
        const condition = str(npc['condition'], 'none')
        const actions: Array<{ kind: NpcModalKind; label: string; visible: boolean }> = [
          { kind: 'saves', label: 'Saving Throw', visible: Array.isArray(npc['savingThrows']) && npc['savingThrows'].length > 0 },
          { kind: 'skills', label: 'Skills', visible: npc['skills'] !== undefined },
          { kind: 'inventory', label: 'Inventory', visible: Array.isArray(npc['equipment']) && npc['equipment'].length > 0 },
          { kind: 'features', label: 'Key Abilities', visible: Array.isArray(npc['classFeatures']) && npc['classFeatures'].length > 0 },
          { kind: 'traits', label: 'Racial Traits', visible: Array.isArray(npc['racialTraits']) && npc['racialTraits'].length > 0 },
          { kind: 'background', label: 'Background', visible: Boolean(rec(npc['backgroundFeature'])?.['name']) },
          { kind: 'spells', label: 'Spells', visible: Boolean(rec(npc['spellcasting']) && Object.keys(rec(npc['spellcasting'])!).length > 0) },
        ]
        const hpColor = tone === 'low' ? '#e74c3c' : tone === 'medium' ? '#e67e22' : 'var(--accent)'
        return (
          <section key={`${name}-${index}`} className="mb-3 rounded border border-card bg-page p-2">
            <div className="flex items-start gap-2 border-b border-card pb-2">
              <div className="min-w-0 flex-1">
                <h3 className="font-display text-base text-primary">{name}</h3>
                <p className="text-xs text-secondary">{str(npc['race'])} {str(npc['class'])} &bull; Level {num(npc['level'], 1)} &bull; {capitalizeWords(str(npc['alignment']))}</p>
              </div>
              {npc['experience_points'] !== undefined && <div className="text-right text-xs"><div className="text-accent">XP</div>{num(npc['experience_points'])} / {num(npc['exp_required_for_next_level'])}</div>}
              {npc['currency'] !== undefined && <div className="grid grid-cols-3 gap-1 text-center text-[10px] text-secondary"><span>{currency.gold}<b className="block text-accent">GP</b></span><span>{currency.silver}<b className="block text-accent">SP</b></span><span>{currency.copper}<b className="block text-accent">CP</b></span></div>}
            </div>
            {npc['abilities'] !== undefined && <div className="mt-2 grid grid-cols-9 gap-1">
              <div className="rounded border border-card p-1 text-center text-[10px]">HP<div className="text-sm">{hp}/{maxHp}</div><div className="h-1 bg-panel"><div className="h-full" style={{ width: `${hpPercent(hp, maxHp)}%`, background: hpColor }} /></div></div>
              <div className="rounded border border-card p-1 text-center text-[10px]">AC<div className="text-sm">{num(npc['armorClass'], 10)}</div></div>
              <div className="rounded border border-card p-1 text-center text-[10px]">INIT<div className="text-sm">{formatModifier(num(npc['initiative']))}</div></div>
              {ABILITIES.map((ability) => <div key={ability} className="rounded border border-card p-1 text-center text-[10px]">{ability.slice(0, 3).toUpperCase()}<div className="text-sm">{scores[ability]}</div><div className="text-accent">{formatModifier(abilityModifier(scores[ability]))}</div></div>)}
            </div>}
            <div className="mt-2 grid grid-cols-2 gap-1">
              {actions.filter((action) => action.visible).map((action) => <button key={action.kind} type="button" className={buttonClass} onClick={() => setSelected({ npc, kind: action.kind })}>{action.label}</button>)}
              <button type="button" disabled aria-hidden="true" className={`${buttonClass} invisible`} />
            </div>
            {(status !== 'alive' || condition !== 'none') && <div className="mt-2 text-xs text-secondary">Status: <span className="text-primary">{status}</span>{condition !== 'none' && <> &nbsp; Condition: <span className="text-primary">{condition}</span></>}</div>}
          </section>
        )
      })}
      {selected && <NpcDetailModal npc={selected.npc} kind={selected.kind} onClose={() => setSelected(null)} />}
    </div>
  )
}
