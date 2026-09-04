/**
 * Pure + DOM helpers backing MapTab (plan Task 7). Kept out of MapTab.tsx so
 * the structural-diffing logic is unit-testable without mounting React or a
 * real SVG layout engine. Auto-fit bbox math, viewBox clamping, and the
 * wheel-zoom/drag-pan handlers are ported from demo/neq-rail.js, the proven
 * mockup implementation referenced by the task brief.
 */
import type { MapDataPayload } from '../../types/map'

export interface ViewBox {
  x: number
  y: number
  w: number
  h: number
}

/** The full 1200x900 map canvas, in mapper-lib's fixed coordinate space. */
export const FULL_VB: ViewBox = { x: 0, y: 0, w: 1200, h: 900 }

/**
 * Fix round 1 (F3): survives MapTab unmount/remount -- e.g. switching away
 * from the Map tab and back -- so a remount can `setRevealed()` the fresh
 * handle straight to where the party had already explored (and restore the
 * last view, fix round 2 N1), instead of replaying the whole reveal
 * animation from an empty map at the default viewBox. This is a client
 * *display* cache only; the server's `mapData.revealed` remains the sole
 * source of truth for what's actually revealed (see MapTab.tsx's module
 * doc). Reset on a genuine area change or when mapData goes null, never
 * merely on unmount. Lives here rather than in MapTab.tsx (fix round 2 N3)
 * so MapTab.tsx exports only the component, keeping React Fast Refresh happy.
 */
export interface MapTabCache {
  key: string
  revealed: string[]
  viewBox: ViewBox
  userTouched: boolean
}
export const mapTabCache: MapTabCache = { key: '', revealed: [], viewBox: FULL_VB, userTouched: false }

/** Test-only: `mapTabCache` is a module singleton, so tests must reset it between cases to stay isolated. */
export function resetMapTabCacheForTests(): void {
  mapTabCache.key = ''
  mapTabCache.revealed = []
  mapTabCache.viewBox = FULL_VB
  mapTabCache.userTouched = false
}

/**
 * A key that changes exactly when the map's rendered structure needs to be
 * rebuilt: a different area, a different room set, or a room whose
 * id/name/type/connections changed (including a redacted room gaining its
 * name+type on first reveal). Connections are sorted so their storage order
 * never affects the key. Rooms are likewise sorted by id so reordering the
 * server's room array alone never triggers a rebuild.
 */
export function structuralKey(payload: MapDataPayload): string {
  const rooms = payload.map.rooms
    .map((r) => `${r.id}|${r.name ?? ''}|${r.type ?? ''}|${[...r.connections].sort().join(',')}`)
    .sort()
    .join(';')
  return `${payload.areaId}:${rooms}`
}

/** Ids present in `next` but not in `prev`, in `next`'s order. Additions only -- the caller is responsible for reveal state never shrinking within an area. */
export function diffReveals(prev: string[], next: string[]): string[] {
  const seen = new Set(prev)
  return next.filter((id) => !seen.has(id))
}

function cssEscape(id: string): string {
  return typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(id) : id.replace(/[^a-zA-Z0-9_-]/g, '\\$&')
}

/** Reads the renderer's `data-anchor="x,y"` from the first room group that carries it. */
export function readAnchor(groups: Iterable<Element>): { x: number; y: number } | null {
  for (const g of groups) {
    const raw = g.getAttribute('data-anchor')
    if (!raw) continue
    const [xs, ys] = raw.split(',')
    const x = Number(xs)
    const y = Number(ys)
    if (Number.isFinite(x) && Number.isFinite(y)) return { x, y }
  }
  return null
}

/**
 * Bounding box of the given revealed room ids' anchors (queried from the
 * rendered [data-room] groups' `data-anchor="x,y"`), padded, aspect-locked
 * to 4:3, and clamped to a sane minimum so a single room isn't absurdly
 * zoomed in. Ported from demo/neq-rail.js::computeAutoFitViewBox.
 */
export function computeAutoFitViewBox(svg: SVGSVGElement, revealedIds: string[]): ViewBox {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const id of revealedIds) {
    const groups = svg.querySelectorAll<SVGGraphicsElement>(`[data-room="${cssEscape(id)}"]`)
    const anchor = readAnchor(groups)
    if (!anchor) continue
    minX = Math.min(minX, anchor.x)
    minY = Math.min(minY, anchor.y)
    maxX = Math.max(maxX, anchor.x)
    maxY = Math.max(maxY, anchor.y)
  }
  if (!isFinite(minX)) return { ...FULL_VB }

  // 280 (was 170): the renderer places room labels outside the glyph, and a
  // long name on a border room was being clipped by the stage edge. The pad is
  // in viewBox units, so it must cover a wrapped two-line label plus its
  // leader tick on every side.
  const PAD = 280
  minX -= PAD
  minY -= PAD
  maxX += PAD
  maxY += PAD
  let w = maxX - minX
  let h = maxY - minY

  const ASPECT = 4 / 3
  if (w / h > ASPECT) h = w / ASPECT
  else w = h * ASPECT

  // MIN_W is a defensive floor, not a reachable clamp with the fixed
  // PAD=280 above: the smallest possible post-pad, post-aspect-lock box (a
  // single zero-size room) is 560x560 padding-only, which aspect-locks to
  // 560*4/3 ≈ 747 -- already well above 400 -- so this branch cannot fire
  // today. Kept in case PAD is ever tuned down; verified unreachable in
  // useMapPanZoom.test.ts.
  const MIN_W = 400
  const MAX_W = 1200
  if (w < MIN_W) {
    w = MIN_W
    h = w / ASPECT
  }
  if (w > MAX_W) {
    w = MAX_W
    h = w / ASPECT
  }

  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  let x = cx - w / 2
  let y = cy - h / 2
  x = Math.min(FULL_VB.w - w, Math.max(0, x))
  y = Math.min(FULL_VB.h - h, Math.max(0, y))
  return { x, y, w, h }
}

export function setViewBox(svg: SVGSVGElement, vb: ViewBox): void {
  svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`)
}

export function zoomPercent(vb: ViewBox): number {
  return Math.round((FULL_VB.w / vb.w) * 100)
}

/**
 * Marks the current-location room group(s) with `.neq-map-here` (interior
 * mode renders two [data-room] groups per room -- walls and floor -- fog.js
 * treats them as a pair, so this does too) and drops a pulsing ring/dot
 * marker at the room's `data-anchor`. Ported from
 * demo/neq-rail.js::markCurrentRoom, generalized to not assume the
 * overland-mode glyph transform (interior mode has no such transform).
 */
export function applyCurrentMarker(svg: SVGSVGElement, currentLocationId: string | null): void {
  for (const el of svg.querySelectorAll('.neq-map-here')) el.classList.remove('neq-map-here')
  svg.querySelector('.neq-map-here-marker')?.remove()
  if (!currentLocationId) return

  const groups = svg.querySelectorAll<SVGGraphicsElement>(`[data-room="${cssEscape(currentLocationId)}"]`)
  if (groups.length === 0) return
  for (const g of groups) g.classList.add('neq-map-here')

  const anchor = readAnchor(groups)
  if (!anchor) return

  const cx = anchor.x
  const cy = anchor.y
  const ns = 'http://www.w3.org/2000/svg'
  const marker = document.createElementNS(ns, 'g')
  marker.setAttribute('class', 'neq-map-here-marker')
  const ring = document.createElementNS(ns, 'circle')
  ring.setAttribute('class', 'neq-map-here-ring')
  ring.setAttribute('cx', String(cx))
  ring.setAttribute('cy', String(cy))
  ring.setAttribute('r', '15')
  const dot = document.createElementNS(ns, 'circle')
  dot.setAttribute('class', 'neq-map-here-dot')
  dot.setAttribute('cx', String(cx))
  dot.setAttribute('cy', String(cy))
  dot.setAttribute('r', '9')
  marker.append(ring, dot)
  svg.append(marker)
}

/**
 * Explorer's Notes row click -> tight pan/zoom to a single room. Ported from
 * demo/neq-notes.js::panToRoom, but centers on the room's `data-anchor` (the
 * same anchor used by the current-room marker) rather than the mockup's own
 * `getRoomCenter` glyph-transform lookup -- one anchor read, two callers,
 * always agreeing on where a room's "center" is.
 */
const FOCUS_PAD = 175
const FOCUS_MIN_W = 300

export function focusRoom(svg: SVGSVGElement, roomId: string, onChange?: (vb: ViewBox) => void): void {
  const groups = svg.querySelectorAll<SVGGraphicsElement>(`[data-room="${cssEscape(roomId)}"]`)
  if (groups.length === 0) return
  const anchor = readAnchor(groups)
  if (!anchor) return

  const cx = anchor.x
  const cy = anchor.y

  const ASPECT = 4 / 3
  let w = FOCUS_PAD * 2
  let h = FOCUS_PAD * 2
  if (w / h > ASPECT) h = w / ASPECT
  else w = h * ASPECT

  if (w < FOCUS_MIN_W) {
    w = FOCUS_MIN_W
    h = w / ASPECT
  }
  if (w > FULL_VB.w) {
    w = FULL_VB.w
    h = w / ASPECT
  }

  let x = cx - w / 2
  let y = cy - h / 2
  x = Math.min(FULL_VB.w - w, Math.max(0, x))
  y = Math.min(FULL_VB.h - h, Math.max(0, y))

  const vb = { x, y, w, h }
  setViewBox(svg, vb)
  onChange?.(vb)
}

const PAN_MIN_W = 240
const PAN_MAX_W = 1200

/** A pointer move shorter than this never counts as a drag -- avoids the view jumping on a click that jiggles a couple of pixels. */
const DRAG_THRESHOLD_PX = 4

/** Clamps a candidate pan/zoom viewBox to the pan-zoom width band and keeps it inside the full 1200x900 canvas. Exported for unit testing; also used internally by wirePanZoom. */
export function clampViewBox(vb: ViewBox): ViewBox {
  const w = Math.min(PAN_MAX_W, Math.max(PAN_MIN_W, vb.w))
  const h = w * (FULL_VB.h / FULL_VB.w)
  const x = Math.min(FULL_VB.w - w, Math.max(0, vb.x))
  const y = Math.min(FULL_VB.h - h, Math.max(0, vb.y))
  return { x, y, w, h }
}

/**
 * Wheel-zoom + drag-pan on `stage`, mutating the current SVG's viewBox
 * directly (no React state in the hot path). Ported from
 * demo/neq-rail.js::wirePanZoom. Returns a cleanup function that removes all
 * listeners; safe to call multiple times.
 */
export function wirePanZoom(
  stage: HTMLElement,
  getSvg: () => SVGSVGElement | null,
  onChange: (vb: ViewBox) => void,
): () => void {
  let dragging: { startX: number; startY: number; vbx: number; vby: number; w: number; moved: boolean } | null = null

  function getViewBox(): ViewBox | null {
    const svg = getSvg()
    if (!svg) return null
    const baseVal = svg.viewBox?.baseVal
    if (baseVal) return { x: baseVal.x, y: baseVal.y, w: baseVal.width, h: baseVal.height }
    // jsdom doesn't implement SVGAnimatedRect -- fall back to parsing the attribute.
    const raw = svg.getAttribute('viewBox')
    if (!raw) return null
    const [x, y, w, h] = raw.trim().split(/\s+/).map(Number)
    if (![x, y, w, h].every(Number.isFinite)) return null
    return { x, y, w, h }
  }

  const onWheel = (e: WheelEvent) => {
    const svg = getSvg()
    const vb = getViewBox()
    const ctm = svg?.getScreenCTM()
    if (!svg || !vb || !ctm) return
    e.preventDefault()
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const loc = pt.matrixTransform(ctm.inverse())
    const factor = Math.exp(e.deltaY * 0.001)
    const newW = vb.w * factor
    const clamped = clampViewBox({
      x: loc.x - (loc.x - vb.x) * (newW / vb.w),
      y: loc.y - (loc.y - vb.y) * (newW / vb.w),
      w: newW,
      h: 0,
    })
    setViewBox(svg, clamped)
    onChange(clamped)
  }

  const onPointerDown = (e: PointerEvent) => {
    const vb = getViewBox()
    if (!vb) return
    dragging = { startX: e.clientX, startY: e.clientY, vbx: vb.x, vby: vb.y, w: vb.w, moved: false }
    if (typeof stage.setPointerCapture === 'function') stage.setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return
    if (!dragging.moved && Math.hypot(e.clientX - dragging.startX, e.clientY - dragging.startY) < DRAG_THRESHOLD_PX) {
      return
    }
    dragging.moved = true
    const svg = getSvg()
    if (!svg) return
    const scale = dragging.w / svg.clientWidth
    const clamped = clampViewBox({
      x: dragging.vbx - (e.clientX - dragging.startX) * scale,
      y: dragging.vby - (e.clientY - dragging.startY) * scale,
      w: dragging.w,
      h: 0,
    })
    setViewBox(svg, clamped)
    onChange(clamped)
  }

  const onPointerUp = (e: PointerEvent) => {
    dragging = null
    if (typeof stage.hasPointerCapture === 'function' && stage.hasPointerCapture(e.pointerId)) {
      stage.releasePointerCapture(e.pointerId)
    }
  }

  // A held drag can end without a pointerup reaching us -- the OS taking the
  // gesture (e.g. a browser back-swipe), a touch getting cancelled, or the
  // capture being lost some other way -- any of which would otherwise leave
  // `dragging` stuck set and the next pointermove would jump the view.
  const onPointerCancel = () => {
    dragging = null
  }

  stage.addEventListener('wheel', onWheel, { passive: false })
  stage.addEventListener('pointerdown', onPointerDown)
  stage.addEventListener('pointermove', onPointerMove)
  stage.addEventListener('pointerup', onPointerUp)
  stage.addEventListener('pointercancel', onPointerCancel)
  stage.addEventListener('lostpointercapture', onPointerCancel)

  return () => {
    stage.removeEventListener('wheel', onWheel)
    stage.removeEventListener('pointerdown', onPointerDown)
    stage.removeEventListener('pointermove', onPointerMove)
    stage.removeEventListener('pointerup', onPointerUp)
    stage.removeEventListener('pointercancel', onPointerCancel)
    stage.removeEventListener('lostpointercapture', onPointerCancel)
  }
}
