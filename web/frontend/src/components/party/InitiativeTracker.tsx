/**
 * InitiativeTracker (plan Task 4.4c) -- combat replacement for the
 * PartyStrip. Renders one chip per combatant (typed player / npc / enemy,
 * color-coded like the legacy tracker), while AdventureBox owns the single
 * round-number badge, and the
 * current-turn highlight: the player's chip glows orange whenever input is
 * unlocked (!isProcessing), the same signal the legacy highlightCurrentTurn()
 * used. Emits request_initiative_data on mount and after every game log
 * update; the initiative_data_response handler writes the single authoritative
 * world.initiative state, from which combat mode is derived. Self-gating: renders nothing
 * while initiative is inactive (PartyStrip shows instead).
 */
import { useEffect, useState } from 'react'
import { usePlayer, useSession, useWorld } from '../../stores'
import { CharacterChip } from './CharacterChip'
import type { ChipVariant } from './CharacterChip'
import { MediaPopup } from './MediaPopup'
import { HorizontalChipRail } from './PartyStrip'
import {
  asString,
  combatantDisplayName,
  initiativeNpcClickMedia,
  initiativeNpcThumbCandidates,
  initiativePlayerThumbCandidates,
  monsterClickMedia,
  monsterThumbCandidates,
  npcClassFallbackPortrait,
} from './media'
import type { ChipKind, ClickMedia, MediaSource } from './media'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { matchingNpc, partySummary } from './partyData'
import { NpcCardDialog } from './NpcCardDialog'
import { PlayerCardDialog } from './PlayerCardDialog'

export function InitiativeTracker() {
  const ember = useEmberDesktop()
  const npcs = usePlayer((s) => s.npcs)
  const npcError = usePlayer((s) => s.dataErrors.npcs)
  const player = usePlayer((s) => s.stats)
  const [selectedNpc, setSelectedNpc] = useState<string | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null)
  const initiative = useWorld((s) => s.initiative)
  const isProcessing = useSession((s) => s.isProcessing)
  const playerName = usePlayer((s) => {
    const value = s.stats ? s.stats['name'] : undefined
    return typeof value === 'string' ? value : null
  })
  const [media, setMedia] = useState<MediaSource | null>(null)
  const rosterIdentity = initiative.combatants.map((entry) => `${asString(entry['type'])}:${asString(entry['name'])}`).sort().join('|')
  useEffect(() => { setMedia(null); setSelectedNpc(null); setSelectedPlayer(null) }, [initiative.active, rosterIdentity, ember])

  // PartyStrip shows instead while combat is inactive.
  if (!initiative.active || initiative.combatants.length === 0) return null

  const renderCombatant = (combatant: Record<string, unknown>) => {
    const name = asString(combatant['name'])
    if (!name) return null
    const rawKind = asString(combatant['type'])
    const kind: ChipKind =
      rawKind === 'player' || rawKind === 'npc' || rawKind === 'enemy' ? rawKind : 'npc'
    const displayName = combatantDisplayName(name, kind)

    let thumbCandidates: string[] = []
    let thumbFallback: string | undefined
    let clickMedia: ClickMedia | undefined
    if (kind === 'enemy') {
      const monsterType = asString(combatant['monsterType'])
      if (monsterType) {
        thumbCandidates = monsterThumbCandidates(monsterType)
        clickMedia = monsterClickMedia(monsterType)
      }
    } else if (kind === 'player') {
      // Legacy combat players have a strict portrait URL and no click media.
      thumbCandidates = initiativePlayerThumbCandidates(name)
    } else {
      thumbCandidates = initiativeNpcThumbCandidates(name)
      thumbFallback = npcClassFallbackPortrait(name)
      clickMedia = initiativeNpcClickMedia(name)
    }

    const variant: ChipVariant =
      kind === 'player' ? 'init-player' : kind === 'npc' ? 'init-npc' : 'init-enemy'

    const projectedController = asString(combatant['controller'])
    const hasTypedOwnership =
      typeof combatant['isCurrent'] === 'boolean' &&
      (projectedController === 'human' || projectedController === 'actor_agent')
    // Typed combat uses the server projection of the committed turn/controller.
    // Absence preserves the legacy input-unlocked/player-name behavior.
    const active = hasTypedOwnership
      ? !isProcessing && combatant['isCurrent'] === true && projectedController === 'human'
      : !isProcessing && kind === 'player' && playerName !== null && playerName === name

    return (
      <CharacterChip
        key={`${kind}:${name}`}
        name={name}
        displayName={displayName}
        variant={variant}
        stats={ember && kind !== 'enemy' ? partySummary(combatant, kind === 'player' ? player : npcError ? undefined : matchingNpc(npcs, name)) : combatant}
        showVitals
        onOpenDetails={ember && kind !== 'enemy' ? () => kind === 'player' ? setSelectedPlayer(name) : setSelectedNpc(name) : undefined}
        thumbCandidates={thumbCandidates}
        thumbFallback={thumbFallback}
        clickMedia={clickMedia}
        active={active}
        onOpenMedia={setMedia}
      />
    )
  }

  return <>
    {initiative.recovery?.required ? (
      <div role="alert" aria-live="assertive" className="combat-recovery-notice">
        {initiative.recovery.message}
      </div>
    ) : null}
    <HorizontalChipRail label="Initiative order" itemCount={initiative.combatants.length}>
      {initiative.combatants.map(renderCombatant)}
    </HorizontalChipRail>
    <MediaPopup media={media} onClose={() => setMedia(null)} />
    {ember && selectedNpc && <NpcCardDialog name={selectedNpc} onClose={() => setSelectedNpc(null)} />}
    {ember && selectedPlayer && <PlayerCardDialog name={selectedPlayer} onClose={() => setSelectedPlayer(null)} />}
  </>
}
