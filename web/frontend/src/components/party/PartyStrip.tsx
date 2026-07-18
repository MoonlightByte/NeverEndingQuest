/**
 * PartyStrip (plan Task 4.4c) -- horizontal chip rail of world.party members
 * plus NPCs present at the location (party_data_response.members /
 * .location_npcs). Emits request_party_data on mount and again after every
 * game log update (the React replacement for the legacy 5s poll), so the
 * strip stays fresh as the DM narrates. Self-gating: renders nothing while
 * world.initiative.active -- InitiativeTracker replaces it during combat.
 */
import { useEffect, useState } from 'react'
import { emitC } from '../../services/socket'
import { useLog, useWorld } from '../../stores'
import { CharacterChip } from './CharacterChip'
import type { ChipVariant } from './CharacterChip'
import { MediaPopup } from './MediaPopup'
import { asString, npcThumbCandidates, partyClickMedia, playerThumbCandidates } from './media'
import type { MediaSource } from './media'

/** Request party data now and after every new log message; returns unsubscribe. */
function requestPartyOnLogActivity(): () => void {
  emitC('request_party_data', undefined)
  const unsubscribe = useLog.subscribe((state, previous) => {
    if (state.messages !== previous.messages) {
      emitC('request_party_data', undefined)
    }
  })
  const timer = window.setInterval(() => emitC('request_party_data', undefined), 5000)
  return () => { unsubscribe(); window.clearInterval(timer) }
}

export function PartyStrip() {
  const party = useWorld((s) => s.party)
  const locationNpcs = useWorld((s) => s.locationNpcs)
  const combatActive = useWorld((s) => s.initiative.active)
  const [media, setMedia] = useState<MediaSource | null>(null)

  useEffect(() => requestPartyOnLogActivity(), [])

  // InitiativeTracker replaces the strip while combat is active.
  if (combatActive) return null
  if (party.length === 0 && locationNpcs.length === 0) return null

  const renderMember = (member: Record<string, unknown>, isLocationNpc: boolean) => {
    const name = asString(member['name'])
    if (!name) return null
    const kind = asString(member['type']) === 'player' ? ('player' as const) : ('npc' as const)
    const variant: ChipVariant = isLocationNpc
      ? 'location-npc'
      : kind === 'player'
        ? 'party-player'
        : 'party-npc'
    return (
      <CharacterChip
        key={`${isLocationNpc ? 'location' : 'party'}:${name}`}
        name={name}
        displayName={name}
        variant={variant}
        stats={member}
        thumbCandidates={kind === 'player' ? playerThumbCandidates(name) : npcThumbCandidates(name)}
        clickMedia={partyClickMedia(name, kind)}
        onOpenMedia={setMedia}
      />
    )
  }

  return (
    <div
      aria-label="Party members"
      className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto"
      style={{ maxHeight: 60, scrollbarWidth: 'none' }}
    >
      {party.map((member) => renderMember(member, false))}
      {locationNpcs.map((npc) => renderMember(npc, true))}
      <MediaPopup media={media} onClose={() => setMedia(null)} />
    </div>
  )
}
