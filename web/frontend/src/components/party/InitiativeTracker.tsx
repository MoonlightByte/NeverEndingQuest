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
import { useState } from 'react'
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

export function InitiativeTracker() {
  const initiative = useWorld((s) => s.initiative)
  const isProcessing = useSession((s) => s.isProcessing)
  const playerName = usePlayer((s) => {
    const value = s.stats ? s.stats['name'] : undefined
    return typeof value === 'string' ? value : null
  })
  const [media, setMedia] = useState<MediaSource | null>(null)

  // PartyStrip shows instead while combat is inactive.
  if (!initiative.active || initiative.combatants.length === 0) return null

  const renderCombatant = (combatant: Record<string, unknown>, index: number) => {
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

    // Legacy parity: input being unlocked signals the player's turn.
    const active =
      !isProcessing && kind === 'player' && playerName !== null && playerName === name

    return (
      <CharacterChip
        key={`${name}:${index}`}
        name={name}
        displayName={displayName}
        variant={variant}
        stats={combatant}
        thumbCandidates={thumbCandidates}
        thumbFallback={thumbFallback}
        clickMedia={clickMedia}
        active={active}
        onOpenMedia={setMedia}
      />
    )
  }

  return <>
    <HorizontalChipRail label="Initiative order" itemCount={initiative.combatants.length}>
      {initiative.combatants.map((combatant, index) => renderCombatant(combatant, index))}
    </HorizontalChipRail>
    <MediaPopup media={media} onClose={() => setMedia(null)} />
  </>
}
