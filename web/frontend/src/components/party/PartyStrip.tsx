/**
 * PartyStrip (plan Task 4.4c) -- horizontal chip rail of world.party members
 * plus NPCs present at the location (party_data_response.members /
 * .location_npcs). Emits request_party_data on mount and again after every
 * game log update (the React replacement for the legacy 5s poll), so the
 * strip stays fresh as the DM narrates. Self-gating: renders nothing while
 * world.initiative.active -- InitiativeTracker replaces it during combat.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { usePlayer, useWorld } from '../../stores'
import { CharacterChip } from './CharacterChip'
import type { ChipVariant } from './CharacterChip'
import { MediaPopup } from './MediaPopup'
import { asString, npcThumbCandidates, partyClickMedia, playerThumbCandidates } from './media'
import type { MediaSource } from './media'
import { useEmberDesktop } from '../layout/EmberPresentation'
import './party-parity.css'
import { matchingNpc, partySummary } from './partyData'
import { NpcCardDialog } from './NpcCardDialog'

interface HorizontalChipRailProps {
  label: string
  itemCount: number
  children: ReactNode
}

/** Shared legacy scroller used by both exploration and initiative rails. */
export function HorizontalChipRail({ label, itemCount, children }: HorizontalChipRailProps) {
  const ember = useEmberDesktop()
  const railRef = useRef<HTMLDivElement>(null)
  const [arrows, setArrows] = useState({ left: false, right: false })

  const updateArrows = useCallback(() => {
    const rail = railRef.current
    if (!rail) return
    const maxScrollLeft = ember ? 0 : Math.max(0, rail.scrollWidth - rail.clientWidth)
    const next = {
      left: maxScrollLeft > 0 && rail.scrollLeft > 0,
      right: maxScrollLeft > 0 && rail.scrollLeft < maxScrollLeft - 1,
    }
    setArrows((current) => current.left === next.left && current.right === next.right ? current : next)
  }, [ember])

  useLayoutEffect(() => {
    const rail = railRef.current
    if (!rail) return undefined
    updateArrows()
    rail.addEventListener('scroll', updateArrows, { passive: true })
    window.addEventListener('resize', updateArrows)
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(updateArrows)
    observer?.observe(rail)
    return () => {
      rail.removeEventListener('scroll', updateArrows)
      window.removeEventListener('resize', updateArrows)
      observer?.disconnect()
    }
  }, [itemCount, updateArrows])

  const scroll = (left: number) => {
    railRef.current?.scrollBy({ left, behavior: 'smooth' })
  }

  const lowerLabel = label.toLowerCase()
  return (
    <div className="neq-chip-scroller-wrapper">
      {arrows.left && <button type="button" aria-label={`Scroll ${lowerLabel} left`} className="neq-chip-scroll-arrow" onClick={() => scroll(-200)}>&lt;</button>}
      <div ref={railRef} aria-label={label} className="neq-chip-scroller">
        {children}
      </div>
      {arrows.right && <button type="button" aria-label={`Scroll ${lowerLabel} right`} className="neq-chip-scroll-arrow" onClick={() => scroll(200)}>&gt;</button>}
    </div>
  )
}

export function PartyStrip() {
  const ember = useEmberDesktop()
  const party = useWorld((s) => s.party)
  const locationNpcs = useWorld((s) => s.locationNpcs)
  const combatActive = useWorld((s) => s.initiative.active)
  const npcs = usePlayer((s) => s.npcs)
  const npcError = usePlayer((s) => s.dataErrors.npcs)
  const player = usePlayer((s) => s.stats)
  const [selectedNpc, setSelectedNpc] = useState<string | null>(null)
  const [media, setMedia] = useState<MediaSource | null>(null)
  const rosterIdentity = [...party, ...locationNpcs].map((entry) => asString(entry['name']) ?? '').sort().join('|')
  useEffect(() => { setMedia(null); setSelectedNpc(null) }, [combatActive, rosterIdentity, ember])

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
        stats={ember ? partySummary(member, kind === 'player' ? player : npcError ? undefined : matchingNpc(npcs, name)) : member}
        showVitals
        onOpenDetails={ember && kind === 'npc' ? () => setSelectedNpc(name) : undefined}
        thumbCandidates={kind === 'player' ? playerThumbCandidates(name) : npcThumbCandidates(name)}
        clickMedia={partyClickMedia(name, kind)}
        onOpenMedia={setMedia}
      />
    )
  }

  return <>
    <HorizontalChipRail label="Party members" itemCount={party.length + locationNpcs.length}>
      {party.map((member) => renderMember(member, false))}
      {ember && locationNpcs.length > 0 && <div className="ember-nearby-label">Nearby</div>}
      {locationNpcs.map((npc) => renderMember(npc, true))}
    </HorizontalChipRail>
    <MediaPopup media={media} onClose={() => setMedia(null)} />
    {ember && selectedNpc && <NpcCardDialog name={selectedNpc} onClose={() => setSelectedNpc(null)} />}
  </>
}
