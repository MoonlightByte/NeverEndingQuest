/**
 * components/party/media.ts -- pure helpers for the party strip / initiative
 * tracker chips: portrait + thumbnail URL candidates, video-else-image click
 * media resolution, and display-name / font-size rules. All URL shapes are
 * ported verbatim from the legacy game_interface.html party display and
 * initiative tracker (served by the Flask /media 3-tier fallback routes and
 * /static). Pure logic + DOM probing only -- no store or socket access.
 */

import { useSyncExternalStore } from 'react'

export interface MediaSource {
  kind: 'video' | 'image'
  src: string
  fallback?: string | null
  anchor?: { top: number; bottom: number; left: number; width: number }
  selection?: { name: string; recipe: ClickMedia; thumbnail: string | null }
}

export interface ClickMedia {
  videoUrl: string
  imageCandidates: string[]
  portraitName?: string
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

/** Exact filename accepted by the existing portrait-upload endpoint. */
export function uploadedPortraitPath(name: string): string {
  return `/static/portraits/${name.toLowerCase().replace(/\s+/g, '_')}.png`
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
  return [...new Set([...candidates, uploadedPortraitPath(name)])]
}

/** Keep the legacy first choice; uploads may retain apostrophes or hyphens. */
export function initiativePlayerThumbCandidates(name: string): string[] {
  return [...new Set([`/static/portraits/${strictFileName(name)}.png`, uploadedPortraitPath(name)])]
}

export function npcThumbCandidates(name: string): string[] {
  return [`/media/npcs/${looseFileName(name)}_thumb.jpg`]
}

/**
 * The initiative renderer historically normalizes only whitespace for NPCs.
 * In particular, apostrophes remain in the URL (unlike the exploration rail).
 */
export function initiativeNpcFileName(name: string): string {
  return name.toLowerCase().replace(/\s+/g, '_')
}

export function initiativeNpcThumbCandidates(name: string): string[] {
  return [`/media/npcs/${initiativeNpcFileName(name)}_thumb.jpg`]
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
    imageCandidates: [...new Set([`${base}.jpg`, `${base}.png`, ...(kind === 'player' ? [uploadedPortraitPath(name)] : [])])],
    ...(kind === 'player' ? { portraitName: name } : {}),
  }
}

/** Legacy initiative NPCs try video, then the single full-size JPG. */
export function initiativeNpcClickMedia(name: string): ClickMedia {
  const base = `/media/npcs/${initiativeNpcFileName(name)}`
  return {
    videoUrl: `${base}_video.mp4`,
    imageCandidates: [`${base}.jpg`],
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
let revision = 0
let globalRevision = 0
const revisions = new Map<string, { version: number; aliases: string[]; uploaded?: string }>()
const listeners = new Set<() => void>()
const entityKey = (name: string) => name.toLowerCase().replace(/\s+/g, '_')
export function mediaVersion(name?: string) {
  return { global: globalRevision, entity: name ? revisions.get(entityKey(name))?.version ?? 0 : 0 }
}
/** Explicit successful upload takes precedence over old aliases/video for this
 * session. Ordinary candidate order/video precedence is otherwise unchanged. */
export function uploadedPortraitCandidates(name: string, candidates: string[]) {
  const uploaded = revisions.get(entityKey(name))?.uploaded
  return uploaded ? [uploaded] : candidates
}
export function invalidateMediaCaches(name?: string, uploadedPortrait = false) {
  imageProbeCache.clear(); videoProbeCache.clear()
  if (name) {
    if (revisions.size >= 256 && !revisions.has(entityKey(name))) { revisions.clear(); globalRevision = ++revision }
    const previous = revisions.get(entityKey(name))
    revisions.set(entityKey(name), {
      version: ++revision,
      aliases: [...new Set([entityKey(name), looseFileName(name), strictFileName(name)])],
      ...(uploadedPortrait ? { uploaded: uploadedPortraitPath(name) } : previous?.uploaded ? { uploaded: previous.uploaded } : {}),
    })
  }
  else { revisions.clear(); globalRevision = ++revision }
  for (const listener of listeners) listener()
}
export function useMediaRevision() {
  return useSyncExternalStore((listener) => {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
  }, () => revision, () => 0)
}
if (typeof window !== 'undefined') window.addEventListener('neq:portrait-updated', (event) => {
  invalidateMediaCaches((event as CustomEvent<{ name?: string }>).detail?.name)
})
function freshUrl(src: string) {
  const [path, query = ''] = src.split('?')
  let stem = path!.split('/').at(-1) ?? ''
  try { stem = decodeURIComponent(stem) } catch { /* Legacy names may contain a literal %. */ }
  const extension = stem.match(/\.[^.]+$/)?.[0].toLowerCase()
  stem = stem.replace(/\.[^.]+$/, '')
  const stems = [stem]
  // Player PNG/JPG filenames are the canonical name, including names such as
  // "Tom Thumb" or "Hero Video". Only generated media routes use image suffixes.
  if (extension === '.mp4') stem = stem.replace(/_video$/, '')
  else if (/^\/media\/(npcs|monsters)\//.test(path!) && (extension === '.jpg' || extension === '.png')) {
    stem = stem.replace(/_thumb$/, '')
  }
  // A full-size NPC named Tom Thumb and Tom's generated thumbnail can share
  // a physical path. Either entity changing must refresh that path.
  if (!stems.includes(stem)) stems.push(stem)
  // Exact stems prevent Ann's revision from shadowing Ann Marie's revision.
  const matches = [...revisions.values()].filter(entry => entry.aliases.some(alias => stems.includes(alias)))
  const version = Math.max(globalRevision, ...matches.map(entry => entry.version))
  if (!version) return src
  const params = new URLSearchParams(query); params.set('neq_media', String(version))
  return `${path}?${params}`
}
function boundedSet(cache: Map<string, Promise<boolean>>, src: string, probe: Promise<boolean>) {
  if (cache.size >= 256) cache.delete(cache.keys().next().value!)
  cache.set(src, probe)
}

export function probeImage(src: string): Promise<boolean> {
  const cached = imageProbeCache.get(src)
  if (cached) return cached
  const probe = new Promise<boolean>((resolve) => {
    if (typeof Image === 'undefined') {
      resolve(false)
      return
    }
    const img = new Image()
    const finish = (ok: boolean) => { clearTimeout(timer); img.onload = null; img.onerror = null; resolve(ok) }
    const timer = setTimeout(() => { finish(false); img.src = '' }, 4000)
    img.onload = () => finish(true)
    img.onerror = () => finish(false)
    img.src = freshUrl(src)
  })
  boundedSet(imageProbeCache, src, probe)
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
    const finish = (ok: boolean) => {
      clearTimeout(timer); video.onloadedmetadata = null; video.onerror = null
      video.removeAttribute?.('src'); video.load?.(); resolve(ok)
    }
    const timer = setTimeout(() => finish(false), 4000)
    video.onloadedmetadata = () => finish(true)
    video.onerror = () => finish(false)
    video.src = freshUrl(src)
  })
  boundedSet(videoProbeCache, src, probe)
  return probe
}

/** First image candidate that actually loads, or null. */
export async function resolveFirstImage(candidates: string[]): Promise<string | null> {
  for (const candidate of candidates) {
    if (await probeImage(candidate)) return freshUrl(candidate)
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
  const uploaded = media.portraitName ? revisions.get(entityKey(media.portraitName))?.uploaded : undefined
  if (uploaded) {
    const image = await resolveFirstImage([uploaded])
    return image ? { kind: 'image', src: image } : null
  }
  if (await probeVideo(media.videoUrl)) {
    return { kind: 'video', src: freshUrl(media.videoUrl), fallback: await resolveFirstImage(media.imageCandidates) ?? thumbFallback }
  }
  const image = await resolveFirstImage(media.imageCandidates)
  if (image) return { kind: 'image', src: image }
  return thumbFallback ? { kind: 'image', src: thumbFallback } : null
}
