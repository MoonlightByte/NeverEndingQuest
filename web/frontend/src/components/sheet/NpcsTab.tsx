import { useEffect, useState } from 'react'
import { CharacterChip } from '../party/CharacterChip'
import { MediaPopup } from '../party/MediaPopup'
import { npcThumbCandidates, partyClickMedia, type MediaSource } from '../party/media'
import '../../theme/ember-npc-media.css'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberCurrency } from './EmberCurrency'
import { usePlayer } from '../../stores'
import { NpcDetailModal, type NpcModalKind } from './NpcDetailModal'
import { matchingNpc } from '../party/partyData'
import { NpcTabbedSheet } from './NpcTabbedSheet'
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
  identity: string
  kind: NpcModalKind
}

export function NpcsTab({ npcName }: { npcName?: string } = {}) {
  const ember = useEmberDesktop()
  const npcs = usePlayer((state) => state.npcs)
  const error = usePlayer((state) => state.dataErrors.npcs)
  const focusedNpc = npcName ? matchingNpc(npcs, npcName) : undefined
  const visibleNpcs = npcName ? (focusedNpc ? [focusedNpc] : []) : npcs
  const [selected, setSelected] = useState<Selection | null>(null)
  const [media, setMedia] = useState<MediaSource | null>(null)
  const rosterIdentity = npcs.map(npcIdentity).sort().join('|')
  useEffect(() => { setMedia(null) }, [rosterIdentity])
  const selectedNpc = selected ? npcs.find((npc) => npcIdentity(npc) === selected.identity) : undefined
  useEffect(() => { if (selected && !selectedNpc) setSelected(null) }, [selected, selectedNpc])

  if (error) return <p role={ember ? 'alert' : undefined} data-state="error" className="ember-sheet-status p-4 font-body text-sm text-red-400">{error}</p>

  return (
    <div className={`neq-npcs-content h-full overflow-y-auto${ember && npcName ? ' tcs-focused-npc' : ''}`}>
      {visibleNpcs.length === 0 ? (
        <p role={ember ? 'status' : undefined} data-state="empty" className="ember-sheet-status text-sm italic text-secondary">{npcName ? 'Full character details are not available for this NPC.' : 'No NPC data available'}</p>
      ) : visibleNpcs.map((npc) => {
        const name = str(npc['name'], 'Unknown NPC')
        const hp = num(npc['hitPoints'])
        const maxHp = num(npc['maxHitPoints'])
        const scores = abilityScores(npc)
        const currency = currencyOf(npc)
        const status = str(npc['status'], 'alive')
        const condition = str(npc['condition']) || (Array.isArray(npc['conditions']) ? npc['conditions'].filter((value) => typeof value === 'string').join(', ') : '') || 'none'
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
        if (ember && npcName) return <NpcTabbedSheet key={npcIdentity(npc)} npc={npc} actions={actions.filter((action) => action.visible)} onSelect={(kind) => { window.dispatchEvent(new CustomEvent('neq:media-request')); setSelected({ identity: npcIdentity(npc), kind }) }} portrait={<CharacterChip name={name} displayName={name} variant="party-npc" stats={npc} thumbCandidates={npcThumbCandidates(name)} clickMedia={partyClickMedia(name, 'npc')} onOpenMedia={setMedia} />} />
        return (
          <section key={npcIdentity(npc)} className="neq-npc-character-sheet">
            <div className="neq-npc-header">
              <CharacterChip name={name} displayName={name} variant="party-npc" stats={npc} thumbCandidates={npcThumbCandidates(name)} clickMedia={partyClickMedia(name, 'npc')} onOpenMedia={setMedia} />
              <div className="neq-npc-header-main">
                <h3 className="neq-npc-name">{name}</h3>
                <p className="neq-npc-details">{`${str(npc['race'])} ${str(npc['class'])} • Level ${num(npc['level'], 1)} • ${capitalizeWords(str(npc['alignment']))}`}</p>
              </div>
              {npc['experience_points'] !== undefined && npc['exp_required_for_next_level'] !== undefined && <div className="neq-npc-header-xp"><div className="neq-xp-label">XP</div><div className="neq-xp-value">{`${num(npc['experience_points'])} / ${num(npc['exp_required_for_next_level'])}`}</div></div>}
              {npc['currency'] !== undefined && (ember ? <EmberCurrency currency={currency} /> : <div className="neq-npc-header-currency"><div className="neq-npc-currency-grid">{([['GP', currency.gold], ['SP', currency.silver], ['CP', currency.copper]] as const).map(([label, value]) => <div key={label} className="neq-npc-currency-item"><span className="neq-npc-currency-amount">{value}</span><span className="neq-npc-currency-type">{label}</span></div>)}</div></div>)}
            </div>
            {(['personality_traits', 'ideals', 'bonds', 'flaws'] as const).some((key) => typeof npc[key] === 'string' && npc[key]) && <dl className="ember-npc-biography">{(['personality_traits', 'ideals', 'bonds', 'flaws'] as const).map((key) => typeof npc[key] === 'string' && npc[key] ? <div key={key}><dt>{capitalizeWords(key.replace(/_/g, ' '))}</dt><dd>{str(npc[key])}</dd></div> : null)}</dl>}
            {npc['abilities'] !== undefined && <div className="neq-npc-abilities">
              <div className="neq-npc-ability-score neq-npc-combat-stat"><div className="neq-npc-ability-name">HP</div><div className="neq-npc-ability-value">{`${hp}/${maxHp}`}</div><div className="neq-npc-hp-bar"><div className={`neq-npc-hp-fill ${hpClass}`} style={{ width: `${hpRatio}%` }} /></div></div>
              <div className="neq-npc-ability-score neq-npc-combat-stat neq-npc-no-circle"><div className="neq-npc-ability-name">AC</div><div className="neq-npc-ability-value">{num(npc['armorClass'], 10)}</div></div>
              <div className="neq-npc-ability-score neq-npc-combat-stat neq-npc-no-circle"><div className="neq-npc-ability-name">INIT</div><div className="neq-npc-ability-value">{formatModifier(num(npc['initiative']))}</div></div>
              {ABILITIES.map((ability) => <div key={ability} className="neq-npc-ability-score"><div className="neq-npc-ability-name">{ability.slice(0, 3).toUpperCase()}</div><div className="neq-npc-ability-value">{scores[ability]}</div><div className="neq-npc-ability-modifier">{formatModifier(abilityModifier(scores[ability]))}</div></div>)}
            </div>}
            <div className="neq-npc-detail-buttons">
              {actions.filter((action) => action.visible).map((action) => <button key={action.kind} type="button" className="neq-npc-detail-button" onClick={() => { window.dispatchEvent(new CustomEvent('neq:media-request')); setSelected({ identity: npcIdentity(npc), kind: action.kind }) }}>{action.label}</button>)}
              <button type="button" disabled aria-hidden="true" className="neq-npc-detail-button neq-npc-detail-spacer" />
            </div>
            {(status !== 'alive' || condition !== 'none') && <div className="neq-npc-status"><div className="neq-npc-status-item">Status: <span className={`neq-npc-status-value ${status}`}>{status}</span></div>{condition !== 'none' && <div className="neq-npc-status-item">Condition: <span className="neq-npc-condition-value">{condition}</span></div>}</div>}
          </section>
        )
      })}
      {selected && selectedNpc && <NpcDetailModal npc={selectedNpc} kind={selected.kind} onClose={() => setSelected(null)} />}
      <MediaPopup media={media} onClose={() => setMedia(null)} />
    </div>
  )
}

function npcIdentity(npc: Record<string, unknown>) { return str(npc['id']) || str(npc['name']) }
