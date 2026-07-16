/**
 * components/party/media.ts -- pure helpers for the party strip / initiative
 * tracker chips: portrait + thumbnail URL candidates, video-else-image click
 * media resolution, and display-name / font-size rules. All URL shapes are
 * ported verbatim from the legacy game_interface.html party display and
 * initiative tracker (served by the Flask /media 3-tier fallback routes and
 * /static). Pure logic + DOM probing only -- no store or socket access.
 */

export interface MediaSource {
  kind: 'video' | 'image'
  src: string
}

export interface ClickMedia {
  videoUrl: string
  imageCandidates: string[]
}

export type ChipKind = 'player' | 'npc' | 'enemy'

// ---------- record field narrowing (party/initiative payloads are Record<string, unknown>) ----------

export function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

export function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined
}

export function asArray(value: unknown): unknown[] | undefined {
  return Array.isArray(value) ? value : undefined
}

// ---------- file-name cleaning (legacy parity) ----------

/** Legacy party-strip cleaning: spaces -> underscores, apostrophes stripped. */
export function looseFileName(name: string): string {
  return name.toLowerCase().replace(/\s+/g, '_').replace(/'/g, '')
}

/** Legacy initiative-player cleaning: anything outside [a-z0-9] -> underscore. */
export function strictFileName(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '_')
}

/** Monster type -> media file stem (e.g. "Dire Wolf" -> "dire_wolf"). */
export function monsterFileName(monsterType: string): string {
  return monsterType.toLowerCase().replace(/\s+/g, '_')
}

/** Legacy singular/plural retry: toggles a trailing "s" on the file stem. */
export function altPluralName(fileName: string): string {
  return fileName.endsWith('s') ? fileName.slice(0, -1) : `${fileName}s`
}

// ---------- thumbnail candidate lists (checked in order, first hit wins) ----------

export function playerThumbCandidates(name: string): string[] {
  const loose = looseFileName(name)
  const strict = strictFileName(name)
  const candidates = [`/static/portraits/${loose}.png`]
  if (strict !== loose) candidates.push(`/static/portraits/${strict}.png`)
  return candidates
}

export function npcThumbCandidates(name: string): string[] {
  return [`/media/npcs/${looseFileName(name)}_thumb.jpg`]
}

export function monsterThumbCandidates(monsterType: string): string[] {
  const stem = monsterFileName(monsterType)
  const alt = altPluralName(stem)
  return [
    `/media/monsters/${stem}_thumb.jpg`,
    `/media/monsters/${stem}_thumb.png`,
    `/media/monsters/${alt}_thumb.jpg`,
    `/media/monsters/${alt}_thumb.png`,
  ]
}

// ---------- click media (video if it exists, else full-size image) ----------

export function partyClickMedia(name: string, kind: 'player' | 'npc'): ClickMedia {
  const base =
    kind === 'player'
      ? `/static/portraits/${looseFileName(name)}`
      : `/media/npcs/${looseFileName(name)}`
  return {
    videoUrl: `${base}_video.mp4`,
    imageCandidates: [`${base}.jpg`, `${base}.png`],
  }
}

export function monsterClickMedia(monsterType: string): ClickMedia {
  const stem = monsterFileName(monsterType)
  const alt = altPluralName(stem)
  return {
    videoUrl: `/media/monsters/${stem}_video.mp4`,
    imageCandidates: [
      `/media/monsters/${stem}.jpg`,
      `/media/monsters/${alt}.jpg`,
      `/media/monsters/${stem}.png`,
      `/media/monsters/${alt}.png`,
    ],
  }
}

// ---------- class-based NPC portrait fallback (legacy keyword order preserved) ----------

const CLASS_PORTRAIT_KEYWORDS: Array<[string[], string]> = [
  [['ranger'], 'ranger'],
  [['scout'], 'rogue'],
  [['cleric'], 'cleric'],
  [['druid'], 'druid'],
  [['paladin'], 'paladin'],
  [['rogue'], 'rogue'],
  [['fighter'], 'fighter'],
  [['barbarian'], 'barbarian'],
  [['monk'], 'monk'],
  [['bard'], 'bard'],
  [['wizard', 'sorcerer', 'warlock', 'mage'], 'wizard'],
]

export function npcClassFallbackPortrait(name: string): string {
  const lower = name.toLowerCase()
  for (const [keywords, portrait] of CLASS_PORTRAIT_KEYWORDS) {
    if (keywords.some((keyword) => lower.includes(keyword))) {
      return `/static/media/class_portraits/${portrait}.png`
    }
  }
  return '/static/media/class_portraits/default_npc.png'
}

// ---------- chip display rules (legacy parity) ----------

/** Underscores -> spaces; enemies/NPCs also drop trailing numbers ("Skeleton_2" -> "Skeleton"). */
export function combatantDisplayName(name: string, kind: ChipKind): string {
  let display = name.replace(/_/g, ' ')
  if (kind === 'enemy' || kind === 'npc') {
    display = display.replace(/\s*\d+\s*$/, '').trim()
  }
  return display
}

/** Dynamic chip label size: <=6 chars 11px, <=10 chars 9px, else 8px. */
export function chipFontSize(displayName: string): number {
  if (displayName.length <= 6) return 11
  if (displayName.length <= 10) return 9
  return 8
}

// ---------- existence probing (results cached per session) ----------

const imageProbeCache = new Map<string, Promise<boolean>>()

export function probeImage(src: string): Promise<boolean> {
  const cached = imageProbeCache.get(src)
  if (cached) return cached
  const probe = new Promise<boolean>((resolve) => {
    if (typeof Image === 'undefined') {
      resolve(false)
      return
    }
    const img = new Image()
    img.onload = () => resolve(true)
    img.onerror = () => resolve(false)
    img.src = src
  })
  imageProbeCache.set(src, probe)
  return probe
}

const videoProbeCache = new Map<string, Promise<boolean>>()

export function probeVideo(src: string): Promise<boolean> {
  const cached = videoProbeCache.get(src)
  if (cached) return cached
  const probe = new Promise<boolean>((resolve) => {
    if (typeof document === 'undefined') {
      resolve(false)
      return
    }
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.onloadedmetadata = () => resolve(true)
    video.onerror = () => resolve(false)
    video.src = src
  })
  videoProbeCache.set(src, probe)
  return probe
}

/** First image candidate that actually loads, or null. */
export async function resolveFirstImage(candidates: string[]): Promise<string | null> {
  for (const candidate of candidates) {
    if (await probeImage(candidate)) return candidate
  }
  return null
}

/**
 * Legacy click behavior: play the video if one exists, else the first
 * full-size image that loads, else the already-resolved thumbnail.
 */
export async function resolveClickMedia(
  media: ClickMedia,
  thumbFallback: string | null,
): Promise<MediaSource | null> {
  if (await probeVideo(media.videoUrl)) {
    return { kind: 'video', src: media.videoUrl }
  }
  const image = await resolveFirstImage(media.imageCandidates)
  if (image) return { kind: 'image', src: image }
  return thumbFallback ? { kind: 'image', src: thumbFallback } : null
}
