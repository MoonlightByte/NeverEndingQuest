/**
 * InitiativeTracker (plan Task 4.4c) -- combat replacement for the
 * PartyStrip. Renders one chip per combatant (typed player / npc / enemy,
 * color-coded like the legacy tracker), a round-number badge, and the
 * current-turn highlight: the player's chip glows orange whenever input is
 * unlocked (!isProcessing), the same signal the legacy highlightCurrentTurn()
 * used. Emits request_initiative_data on mount and after every game log
 * update; the initiative_data_response handler in services/socket.ts writes
 * world.initiative AND session.setCombatActive, so this request loop is what
 * drives session.mode into and out of 'combat'. Self-gating: renders nothing
 * while initiative is inactive (PartyStrip shows instead).
 */
import { useEffect, useState } from 'react'
import { emitC } from '../../services/socket'
import { useLog, usePlayer, useSession, useWorld } from '../../stores'
import { CharacterChip } from './CharacterChip'
import type { ChipVariant } from './CharacterChip'
import { MediaPopup } from './MediaPopup'
import {
  asString,
  combatantDisplayName,
  monsterClickMedia,
  monsterThumbCandidates,
  npcClassFallbackPortrait,
  npcThumbCandidates,
  partyClickMedia,
  playerThumbCandidates,
} from './media'
import type { ChipKind, ClickMedia, MediaSource } from './media'

/** Request initiative data now and after every new log message; returns unsubscribe. */
function requestInitiativeOnLogActivity(): () => void {
  emitC('request_initiative_data', undefined)
  return useLog.subscribe((state, previous) => {
    if (state.messages !== previous.messages) {
      emitC('request_initiative_data', undefined)
    }
  })
}

function RoundBadge({ round }: { round: number }) {
  return (
    <div
      aria-label={`Combat round ${round}`}
      className="flex h-[60px] w-[52px] shrink-0 flex-col items-center justify-center rounded-md text-center"
      style={{
        backgroundColor: '#1e1e1e',
        border: '2px solid #555',
        boxShadow: 'inset 0 0 8px rgba(0,0,0,0.6)',
      }}
    >
      <div
        className="font-display font-bold uppercase"
        style={{ fontSize: 10, color: '#888', letterSpacing: 1, lineHeight: 1 }}
      >
        Round
      </div>
      <div className="font-bold" style={{ fontSize: 20, color: 'var(--accent)', lineHeight: 1.1 }}>
        {round}
      </div>
    </div>
  )
}

export function InitiativeTracker() {
  const initiative = useWorld((s) => s.initiative)
  const isProcessing = useSession((s) => s.isProcessing)
  const playerName = usePlayer((s) => {
    const value = s.stats ? s.stats['name'] : undefined
    return typeof value === 'string' ? value : null
  })
  const [media, setMedia] = useState<MediaSource | null>(null)

  useEffect(() => requestInitiativeOnLogActivity(), [])

  // PartyStrip shows instead while combat is inactive.
  if (!initiative.active || initiative.combatants.length === 0) return null

  const round = initiative.round > 0 ? initiative.round : 1

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
      thumbCandidates = playerThumbCandidates(name)
      clickMedia = partyClickMedia(name, 'player')
    } else {
      thumbCandidates = npcThumbCandidates(name)
      thumbFallback = npcClassFallbackPortrait(name)
      clickMedia = partyClickMedia(name, 'npc')
    }

    const variant: ChipVariant =
      kind === 'player' ? 'init-player' : kind === 'npc' ? 'init-npc' : 'init-enemy'

    // Legacy parity: input being unlocked signals the player's turn.
    const active =
      !isProcessing && kind === 'player' && (playerName === null || playerName === name)

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

  return (
    <div
      aria-label="Initiative order"
      className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto"
      style={{ maxHeight: 60, scrollbarWidth: 'none' }}
    >
      <RoundBadge round={round} />
      {initiative.combatants.map((combatant, index) => renderCombatant(combatant, index))}
      <MediaPopup media={media} onClose={() => setMedia(null)} />
    </div>
  )
}
