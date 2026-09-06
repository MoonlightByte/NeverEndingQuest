/**
 * CharacterChip (plan Task 4.4c) -- one 60x60 portrait chip, shared by
 * PartyStrip (party member / location NPC variants) and InitiativeTracker
 * (player / npc / enemy combatant variants). Resolves its thumbnail from the
 * /media + /static candidate lists (with optional class-portrait fallback),
 * shows the StatsTooltip on hover (50ms show / 100ms hide debounce, legacy
 * parity), and on click resolves video-else-image media for the MediaPopup.
 */
import { useEffect, useRef, useState } from 'react'
import { StatsTooltip } from './StatsTooltip'
import { chipFontSize, probeImage, resolveClickMedia, resolveFirstImage, uploadedPortraitCandidates, useMediaRevision } from './media'
import type { ClickMedia, MediaSource } from './media'
import './party-parity.css'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberInspection } from '../sheet/EmberInspection'

export type ChipVariant =
  | 'party-player'
  | 'party-npc'
  | 'location-npc'
  | 'init-player'
  | 'init-npc'
  | 'init-enemy'

interface VariantStyle {
  border: string
  background: string
  glow: string
  opacity?: number
}

/** Border / glow color coding ported from the legacy chip CSS. */
const VARIANT_STYLE: Record<ChipVariant, VariantStyle> = {
  'party-player': {
    border: '#ff9800',
    background: '#1e1e1e',
    glow: '0 0 5px rgba(255, 152, 0, 0.3)',
  },
  'party-npc': {
    border: '#4CAF50',
    background: '#1e1e1e',
    glow: '0 0 5px rgba(76, 175, 80, 0.3)',
  },
  'location-npc': {
    border: '#9C27B0',
    background: '#1e1e1e',
    glow: 'none',
    opacity: 0.8,
  },
  'init-player': { border: '#4a90e2', background: 'rgba(74, 144, 226, 0.1)', glow: 'none' },
  'init-npc': { border: '#4CAF50', background: 'rgba(76, 175, 80, 0.1)', glow: 'none' },
  'init-enemy': { border: '#f44336', background: 'rgba(244, 67, 54, 0.1)', glow: 'none' },
}

export interface CharacterChipProps {
  name: string
  displayName: string
  variant: ChipVariant
  /** Raw member / combatant record -- fed to the StatsTooltip. */
  stats: Record<string, unknown>
  /** Thumbnail URLs probed in order; first hit becomes the background. */
  thumbCandidates: string[]
  /** Optional class-portrait fallback when no candidate loads (initiative NPCs). */
  thumbFallback?: string | undefined
  /** Click media (video-else-image); omit to disable the media popup. */
  clickMedia?: ClickMedia | undefined
  /** Current-turn highlight (initiative tracker only). */
  active?: boolean | undefined
  onOpenMedia: (media: MediaSource) => void
}

export function CharacterChip({
  name,
  displayName,
  variant,
  stats,
  thumbCandidates,
  thumbFallback,
  clickMedia,
  active,
  onOpenMedia,
}: CharacterChipProps) {
  const ember = useEmberDesktop()
  const mediaRevision = useMediaRevision()
  const requestId = useRef(0)
  const chipRef = useRef<HTMLButtonElement>(null)
  const showTimer = useRef<number | null>(null)
  const hideTimer = useRef<number | null>(null)
  const [thumb, setThumb] = useState<string | null>(null)
  const [hovered, setHovered] = useState(false)
  const [mediaPending, setMediaPending] = useState(false)
  const [mediaMissing, setMediaMissing] = useState(false)

  const thumbKey = thumbCandidates.join('|')
  useEffect(() => {
    let alive = true
    setThumb(null)
    setMediaPending(false); setMediaMissing(false)
    void (async () => {
      const candidates = variant === 'party-player' || variant === 'init-player' ? uploadedPortraitCandidates(name, thumbCandidates) : thumbCandidates
      const resolved = await resolveFirstImage(candidates)
      if (!alive) return
      if (resolved) {
        setThumb(resolved)
        return
      }
      if (thumbFallback && (await probeImage(thumbFallback)) && alive) {
        setThumb(thumbFallback)
      }
    })()
    return () => {
      alive = false
      requestId.current++
    }
    // thumbKey stands in for the candidates array identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thumbKey, thumbFallback, mediaRevision, name, variant])

  useEffect(
    () => () => {
      if (showTimer.current !== null) window.clearTimeout(showTimer.current)
      if (hideTimer.current !== null) window.clearTimeout(hideTimer.current)
    },
    [],
  )

  const handleMouseEnter = () => {
    if (hideTimer.current !== null) window.clearTimeout(hideTimer.current)
    showTimer.current = window.setTimeout(() => setHovered(true), 50)
  }

  const handleMouseLeave = () => {
    if (showTimer.current !== null) window.clearTimeout(showTimer.current)
    hideTimer.current = window.setTimeout(() => setHovered(false), 100)
  }

  const handleClick = () => {
    if (!clickMedia) return
    setHovered(false)
    if (showTimer.current !== null) window.clearTimeout(showTimer.current)
    window.dispatchEvent(new CustomEvent('neq:media-request'))
    const id = ++requestId.current
    setMediaPending(true); setMediaMissing(false)
    void resolveClickMedia(clickMedia, thumb).then((media) => {
      if (id !== requestId.current || !chipRef.current?.isConnected) return
      setMediaPending(false); setMediaMissing(!media)
      if (media && id === requestId.current && chipRef.current?.isConnected) {
        const rect = chipRef.current?.getBoundingClientRect()
        const selection = { name, recipe: clickMedia, thumbnail: thumb }
        onOpenMedia(rect ? {
          ...media,
          selection,
          anchor: { top: rect.top, bottom: rect.bottom, left: rect.left, width: rect.width },
        } : { ...media, selection })
      }
    })
  }

  useEffect(() => {
    const cancel = () => { requestId.current++; setHovered(false); setMediaPending(false); setMediaMissing(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') cancel() }
    window.addEventListener('keydown', escape)
    window.addEventListener('neq:media-request', cancel)
    return () => { window.removeEventListener('keydown', escape); window.removeEventListener('neq:media-request', cancel) }
  }, [])

  const variantStyle = VARIANT_STYLE[variant]
  const isActive = active === true
  const isPartyHover = hovered && (variant === 'party-player' || variant === 'party-npc')
  const isLocationHover = hovered && variant === 'location-npc'
  const isEnemyMediaHover = hovered && variant === 'init-enemy' && clickMedia !== undefined
  const hoverTransform = isPartyHover || isLocationHover || isEnemyMediaHover
    ? 'scale(1.05)'
    : undefined
  const hoverShadow = isPartyHover
    ? '0 0 10px rgba(255, 152, 0, 0.5)'
    : isLocationHover
      ? '0 0 10px rgba(156, 39, 176, 0.5)'
      : undefined

  return (
    <div className={ember ? 'ember-person-entry' : 'contents'}>
      <button
        ref={chipRef}
        type="button"
        aria-label={displayName}
        aria-busy={mediaPending}
        aria-current={ember && isActive ? 'step' : undefined}
        data-chip={variant}
        data-name={name}
        data-active={isActive ? 'true' : 'false'}
        data-media-enabled={clickMedia ? 'true' : 'false'}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleMouseEnter}
        onBlur={handleMouseLeave}
        className={`neq-character-chip neq-character-chip-${variant} relative flex h-[60px] w-[60px] shrink-0 items-end justify-center overflow-hidden rounded p-0.5 text-center font-bold`}
        style={{
          border: `2px solid ${isActive ? '#FFA500' : variantStyle.border}`,
          backgroundColor: isActive ? '#3a3a3a' : variantStyle.background,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          // Legacy assigns white inline after installing the thumbnail URL,
          // even when that image ultimately falls back at paint time.
          color: '#fff',
          boxShadow: isActive
            ? '0 0 15px rgba(255, 165, 0, 0.7)'
            : hoverShadow ?? variantStyle.glow,
          cursor: clickMedia ? 'pointer' : 'default',
          ...(thumb && !ember ? { backgroundImage: `url('${thumb}')` } : {}),
          ...(variantStyle.opacity !== undefined
            ? { opacity: isLocationHover ? 1 : variantStyle.opacity }
            : isEnemyMediaHover
              ? { opacity: 0.8 }
              : {}),
          ...(isActive
            ? { transform: 'scale(1.08)', zIndex: 5 }
            : hoverTransform
              ? { transform: hoverTransform }
              : {}),
        }}
      >
        {ember && <span className="ember-chip-portrait" aria-hidden="true" style={thumb ? { backgroundImage: `url('${thumb}')` } : undefined}>{!thumb && displayName.slice(0, 1)}</span>}
        <span
          className="w-full break-words"
          style={{
            fontSize: chipFontSize(displayName),
            lineHeight: 1.1,
            marginBottom: 2,
            textShadow: '1px 1px 2px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.8)',
          }}
        >
          {displayName}
          {ember && isActive && <small className="ember-turn-label">Your turn</small>}
          {mediaPending && <small className="ember-turn-label" role="status">Loading media…</small>}
          {mediaMissing && <small className="ember-turn-label" role="status">No media available</small>}
        </span>
      </button>
      {ember && <EmberInspection label={`${displayName} statistics`} triggerContent="Details" className="ember-person-details"><StatsTooltip stats={stats} anchor={null} inline /></EmberInspection>}
      {hovered && <StatsTooltip stats={stats} anchor={chipRef.current} />}
    </div>
  )
}
