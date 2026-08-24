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

/**
 * Bounding box of the given revealed room ids (queried from the rendered
 * [data-room] groups), padded, aspect-locked to 4:3, and clamped to a sane
 * minimum so a single room isn't absurdly zoomed in. Ported from
 * demo/neq-rail.js::computeAutoFitViewBox.
 *
 * Anchors on each room's icon/label cluster via `markerAnchorBBox` (the same
 * outlier-filtered anchor used for the current-room marker and notes-row
 * focus) rather than the raw union of the full `[data-room]` group bbox.
 * At `labelScale:2` the clamped/de-collided label text can be large and, on
 * dense maps, pushed well past its room's icon -- unioning the whole group
 * let a handful of oversized/offset labels skew the computed fit (zoomed out
 * further than the actually-revealed rooms warrant, off-center). Anchoring
 * on icon centers keeps the fit tied to where the rooms actually are.
 */
export function computeAutoFitViewBox(svg: SVGSVGElement, revealedIds: string[]): ViewBox {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const id of revealedIds) {
    const groups = svg.querySelectorAll<SVGGraphicsElement>(`[data-room="${cssEscape(id)}"]`)
    const anchor = markerAnchorBBox(groups)
    if (!anchor) continue
    minX = Math.min(minX, anchor.x)
    minY = Math.min(minY, anchor.y)
    maxX = Math.max(maxX, anchor.x + anchor.width)
    maxY = Math.max(maxY, anchor.y + anchor.height)
  }
  if (!isFinite(minX)) return { ...FULL_VB }

  const PAD = 170
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
  // PAD=170 above: the smallest possible post-pad, post-aspect-lock box (a
  // single zero-size room) is 340x340 padding-only, which aspect-locks to
  // 340*4/3 ≈ 453 -- already above 400 -- so this branch cannot fire today.
  // Kept in case PAD is ever tuned down; verified unreachable in
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

type BBox = { x: number; y: number; width: number; height: number }

/**
 * Backport (Task 8/9 legacy fix, web/static/js/mapper-glue.js): the
 * current-room pulse marker was landing on blank parchment, offset ~90px
 * from the room's actual glyph, on overland maps -- NOT a
 * "currentLocationId missing from revealed[]" data problem (the
 * server-projected payload always includes it). Root cause: the vendored
 * mapper's overland renderer (render.js) nests each room's
 * nearest-neighbor-assigned decorative terrain glyphs (planFlavor's
 * scattered moss/tree/reed marks) inside the SAME `<g data-room="id">` as
 * that room's actual icon+label. Those decorations can span a bbox 50-300x
 * larger in area than the icon, because "nearest room" assignment scatters
 * them across whatever empty map area is closest -- not tightly around the
 * glyph. Unioning the *whole* `[data-room]` group's bbox (this function's
 * original approach) puts the computed center wherever that lopsided union
 * happens to fall, not on the glyph.
 *
 * Computes the union bbox of each matched group's *direct children*
 * instead, dropping any child whose area is a large outlier relative to the
 * smallest sibling. Measured on a real payload (see mapper-glue.js and
 * task-8-report.md): glyph icon ~420px^2, name label ~4000px^2, type tag
 * ~430px^2, decoration group ~118,000px^2 (280x the icon) -- a wide,
 * deliberately generous OUTLIER_MULTIPLE cleanly separates "icon + labels"
 * from "scattered decorations" without hardcoding anything about the
 * vendored renderer's internal filter IDs or child ordering. Interior-mode
 * rooms have no such decorations (planFlavor only runs for overland maps --
 * render.js passes `decos = interior ? [] : planFlavor(...)`), so every
 * interior child bbox is already room-sized and comparable; nothing gets
 * dropped there, which preserves the original whole-room-bbox behavior
 * interior mode wants.
 *
 * `groups` is the live NodeList/array of one-or-more `[data-room]` elements
 * for the current room (one for overland, two -- walls + floor -- for
 * interior).
 */
export function markerAnchorBBox(groups: Iterable<SVGGraphicsElement>): BBox | null {
  const OUTLIER_MULTIPLE = 15
  let boxes: BBox[] = []
  for (const group of groups) {
    const kids = group.children
    if (kids.length === 0) {
      try {
        const own = group.getBBox()
        if (own.width > 0 || own.height > 0) boxes.push(own)
      } catch {
        // jsdom / not-yet-laid-out SVG: skip, marker circle just won't be placed
      }
      continue
    }
    for (const kid of kids) {
      try {
        const b = (kid as unknown as SVGGraphicsElement).getBBox()
        if (b.width > 0 || b.height > 0) boxes.push(b)
      } catch {
        // jsdom / not-yet-laid-out SVG: skip this child
      }
    }
  }
  if (boxes.length === 0) return null

  if (boxes.length > 1) {
    let minArea = Infinity
    for (const b of boxes) minArea = Math.min(minArea, b.width * b.height)
    if (minArea > 0) {
      const kept = boxes.filter((b) => b.width * b.height <= minArea * OUTLIER_MULTIPLE)
      if (kept.length > 0) boxes = kept
    }
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const b of boxes) {
    minX = Math.min(minX, b.x)
    minY = Math.min(minY, b.y)
    maxX = Math.max(maxX, b.x + b.width)
    maxY = Math.max(maxY, b.y + b.height)
  }
  if (!isFinite(minX)) return null
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

/**
 * Marks the current-location room group(s) with `.neq-map-here` (interior
 * mode renders two [data-room] groups per room -- walls and floor -- fog.js
 * treats them as a pair, so this does too) and drops a pulsing ring/dot
 * marker at a bbox center computed by `markerAnchorBBox` above. Ported from
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

  const anchor = markerAnchorBBox(groups)
  if (!anchor) return

  const cx = anchor.x + anchor.width / 2
  const cy = anchor.y + anchor.height / 2
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
 * demo/neq-notes.js::panToRoom, but centers on the room's icon/label cluster
 * via `markerAnchorBBox` (the anchor already used by the current-room
 * marker) rather than the mockup's own `getRoomCenter` glyph-transform
 * lookup -- one anchor computation, two callers, always agreeing on where a
 * room's "center" is.
 */
const FOCUS_PAD = 175
const FOCUS_MIN_W = 300

export function focusRoom(svg: SVGSVGElement, roomId: string, onChange?: (vb: ViewBox) => void): void {
  const groups = svg.querySelectorAll<SVGGraphicsElement>(`[data-room="${cssEscape(roomId)}"]`)
  if (groups.length === 0) return
  const anchor = markerAnchorBBox(groups)
  if (!anchor) return

  const cx = anchor.x + anchor.width / 2
  const cy = anchor.y + anchor.height / 2

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
  let dragging: { startX: number; startY: number; vbx: number; vby: number; w: number } | null = null

  function getViewBox(): ViewBox | null {
    const svg = getSvg()
    if (!svg) return null
    const vb = svg.viewBox.baseVal
    return { x: vb.x, y: vb.y, w: vb.width, h: vb.height }
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
    dragging = { startX: e.clientX, startY: e.clientY, vbx: vb.x, vby: vb.y, w: vb.w }
    stage.setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return
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
    if (stage.hasPointerCapture(e.pointerId)) stage.releasePointerCapture(e.pointerId)
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
