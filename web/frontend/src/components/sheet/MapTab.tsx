/**
 * Map tab (plan Task 7): spoiler-safe fog-of-war map for the party's current
 * area, rendered by the vendored mapper library against the server's
 * MapDataPayload projection. Auto-fit/pan-zoom/current-room pulse are ported
 * from demo/neq-rail.html, the proven mockup referenced by the task brief.
 *
 * The server's visited-room set is the only source of truth for what's
 * revealed -- this component never invents reveal state of its own;
 * `mapData.revealed` is re-applied (grown OR shrunk) on every payload. A
 * shrink (e.g. a campaign reset re-fogging rooms) can't be expressed as an
 * animated delta, so it goes through `setRevealed` instead of `reveal()`.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createMap, type MapperHandle } from 'mapper-lib'
import { useWorld } from '../../stores'
import type { MapRoom } from '../../types/map'
import {
  FULL_VB,
  applyCurrentMarker,
  computeAutoFitViewBox,
  diffReveals,
  focusRoom,
  mapTabCache as cache,
  setViewBox,
  structuralKey,
  wirePanZoom,
  zoomPercent,
  type ViewBox,
} from './useMapPanZoom'
import '../../theme/im-fell-fonts.css'
import './MapTab.css'

/** A discovered room: one that has been revealed and so carries a name (see MapRoom's SECURITY NOTE cross-reference in types/map.ts). */
type DiscoveredRoom = MapRoom & { name: string }

export function MapTab() {
  const mapData = useWorld((s) => s.mapData)

  const stageRef = useRef<HTMLDivElement>(null)
  const notesScrollRef = useRef<HTMLDivElement>(null)
  const currentRowRef = useRef<HTMLButtonElement>(null)
  const handleRef = useRef<MapperHandle | null>(null)
  const keyRef = useRef(cache.key)
  const userTouchedRef = useRef(cache.userTouched)
  const panZoomCleanupRef = useRef<(() => void) | null>(null)
  const [zoomPct, setZoomPct] = useState(zoomPercent(cache.viewBox))
  const [focusedRowId, setFocusedRowId] = useState<string | null>(null)

  // Explorer's Notes: discovered rooms are simply the ones the server chose
  // to name (see types/map.ts -- unrevealed rooms never carry name/type), in
  // id order so the list doesn't reshuffle as new rooms get revealed out of
  // discovery order.
  const discovered = useMemo<DiscoveredRoom[]>(() => {
    if (!mapData) return []
    return mapData.map.rooms
      .filter((r): r is DiscoveredRoom => Boolean(r.name))
      .sort((a, b) => a.id.localeCompare(b.id))
  }, [mapData])
  const totalCount = mapData?.map.rooms.length ?? 0
  // discovered.length (not revealed.length) so the header "N of M" and this
  // line always sum to M, matching the approved mockup, even if a revealed
  // room ever arrives unnamed.
  const undiscoveredCount = mapData ? totalCount - discovered.length : 0

  // Shared by wheel-zoom/drag-pan (wirePanZoom's onChange) and an Explorer's
  // Notes row click (focusRoom's onChange) -- both are "the user chose a
  // view", so both mark userTouched and persist the resulting viewBox the
  // same way the D1 full-map click already does.
  function markTouched(vb: ViewBox) {
    userTouchedRef.current = true
    cache.userTouched = true
    cache.viewBox = vb
    setZoomPct(zoomPercent(vb))
  }

  useEffect(() => {
    const el = stageRef.current
    if (!el) return

    if (!mapData) {
      // F5: nothing to show (no active area yet, or a campaign reset) --
      // tear down any previously rendered map rather than leaving a stale
      // one sitting under the placeholder overlay.
      if (handleRef.current) {
        panZoomCleanupRef.current?.()
        panZoomCleanupRef.current = null
        handleRef.current.destroy()
        handleRef.current = null
      }
      keyRef.current = ''
      cache.key = ''
      cache.revealed = []
      return
    }

    const structural = structuralKey(mapData)
    // Rebuild when the structure actually changed, OR when this effect run
    // has no live handle to work with (first mount of a fresh component
    // instance, or the handle was torn down by an unmount/StrictMode
    // cleanup since the last run) -- `structural === keyRef.current` alone
    // isn't enough to prove a handle exists.
    if (structural !== keyRef.current || !handleRef.current) {
      const sameArea = keyRef.current.startsWith(mapData.areaId + ':')
      // Only an AREA change invalidates the row-focus highlight -- room ids
      // can recur across areas/modules, so a stale focusedRowId could light
      // up an unrelated row in the new map. A same-area structural change
      // (e.g. discovering a new room) leaves any already-focused row's id
      // still valid, so the highlight should survive it (F5).
      if (!sameArea) setFocusedRowId(null)
      const prevRevealed = sameArea ? (handleRef.current?.revealed() ?? cache.revealed) : []
      handleRef.current?.destroy()
      handleRef.current = createMap(el, mapData.map, mapData.area, { uid: 'neqmap', fontCss: false, quiet: true, labelScale: 2 })
      handleRef.current.setRevealed(prevRevealed.filter((id) => mapData.revealed.includes(id)))
      keyRef.current = structural
      cache.key = structural
      if (!sameArea) {
        // N1(b): a cross-area move must also drop the *cached* touched/view
        // state, not just the ref -- otherwise a pan in area A permanently
        // suppresses auto-fit on every future remount into area B (the ref
        // is per-instance and would reset fine on its own, but a remount
        // re-seeds it FROM this same cache, so a stale cache.userTouched=true
        // would immediately re-arm the suppression).
        userTouchedRef.current = false
        cache.userTouched = false
        cache.viewBox = FULL_VB
      } else if (userTouchedRef.current) {
        // N1(a): a same-area rebuild (e.g. remount after a tab switch, or a
        // structural change like a redacted room getting its name) creates a
        // brand-new SVG at mapper-lib's default full-map viewBox. If the
        // user had manually panned/zoomed before, restore that view instead
        // of silently reverting to full-map while the zoom indicator (seeded
        // from the same cache) claims otherwise.
        setViewBox(handleRef.current.svg, cache.viewBox)
        setZoomPct(zoomPercent(cache.viewBox))
      }
    }

    const handle = handleRef.current
    if (!handle) return

    // F2: the server's revealed set can shrink (a reset re-fogging rooms),
    // not just grow. A shrink can't be expressed as an animated delta, so
    // detect it and hand the whole set to setRevealed (fog.js handles
    // hiding previously-shown rooms); otherwise animate just the additions.
    const currentRevealed = handle.revealed()
    const shrunk = currentRevealed.some((id) => !mapData.revealed.includes(id))
    if (shrunk) {
      handle.setRevealed(mapData.revealed)
    } else {
      for (const id of diffReveals(currentRevealed, mapData.revealed)) handle.reveal(id)
    }
    cache.revealed = handle.revealed()

    // React#7 (defensive): only draw the "you are here" marker when the
    // current room is actually in the revealed set. The server projection
    // guarantees current in revealed, but if that invariant ever slipped,
    // rendering the marker on a fogged (opacity-0) room would leak the
    // party's position -- so guard it client-side too.
    const currentIsRevealed = mapData.currentLocationId !== null && mapData.revealed.includes(mapData.currentLocationId)
    applyCurrentMarker(handle.svg, currentIsRevealed ? mapData.currentLocationId : null)

    if (!userTouchedRef.current) {
      const fit = computeAutoFitViewBox(handle.svg, mapData.revealed)
      cache.viewBox = fit
      setViewBox(handle.svg, fit)
      setZoomPct(zoomPercent(fit))
    }

    if (!panZoomCleanupRef.current) {
      panZoomCleanupRef.current = wirePanZoom(
        el,
        () => handleRef.current?.svg ?? null,
        // N1(a) needs markTouched's cache.viewBox write: without it,
        // cache.viewBox only ever reflects the last auto-fit/reset/full-map
        // viewBox, never a live wheel-zoom/drag-pan position, so a same-area
        // remount would restore the wrong view.
        markTouched,
      )
    }
  }, [mapData])

  // StrictMode-safe unmount: tears down pan/zoom listeners and the rendered
  // SVG so a remount never finds a dangling handle from a prior mount. Does
  // NOT clear keyRef/cache (F3) -- the next mount's effect run detects the
  // missing handle via `!handleRef.current` above and rebuilds, but reuses
  // the cached revealed/view state instead of animating from scratch.
  useEffect(
    () => () => {
      panZoomCleanupRef.current?.()
      panZoomCleanupRef.current = null
      handleRef.current?.destroy()
      handleRef.current = null
    },
    [],
  )

  function handleReset() {
    const svg = handleRef.current?.svg
    if (!svg || !mapData) return
    // F4: recompute fresh rather than trusting a cached fit, which only
    // reflects whatever was revealed the last time auto-fit ran -- stale if
    // the party explored more rooms while the user had manually panned/
    // zoomed (auto-fit is skipped while userTouchedRef is true).
    const fit = computeAutoFitViewBox(svg, mapData.revealed)
    cache.viewBox = fit
    userTouchedRef.current = false
    cache.userTouched = false
    setViewBox(svg, fit)
    setZoomPct(zoomPercent(fit))
  }

  function handleFull() {
    const svg = handleRef.current?.svg
    if (!svg) return
    userTouchedRef.current = true
    cache.userTouched = true
    // D1: full-map is a user view choice like any pan/zoom -- persist it so a
    // same-area remount restores full-map, not the previous cached view.
    cache.viewBox = FULL_VB
    setViewBox(svg, FULL_VB)
    setZoomPct(zoomPercent(FULL_VB))
  }

  // Explorer's Notes row click: tight pan/zoom to that room (ported from
  // demo/neq-notes.js::onRowClick) plus the mockup's is-focused row
  // highlight.
  function handleRowClick(roomId: string) {
    const svg = handleRef.current?.svg
    if (!svg) return
    setFocusedRowId(roomId)
    focusRoom(svg, roomId, markTouched)
  }

  // The party's current room must always be visible on load/relocation --
  // scroll the notes list just far enough to bring it into view, without
  // disturbing the id-ordered layout otherwise. Manual scrollTop math (not
  // scrollIntoView): the latter also scrolls the overflow:hidden card
  // ancestor, dragging the pinned header out of view -- see
  // demo/neq-notes.js::buildNotesPanel for the same comment against the
  // mockup this is ported from.
  useEffect(() => {
    const scrollEl = notesScrollRef.current
    const currentRow = currentRowRef.current
    if (!scrollEl || !currentRow) return
    const raf = requestAnimationFrame(() => {
      const bottom = currentRow.offsetTop + currentRow.offsetHeight
      const view = scrollEl.clientHeight
      if (bottom > scrollEl.scrollTop + view) {
        scrollEl.scrollTop = bottom - view + 8
      } else if (currentRow.offsetTop < scrollEl.scrollTop) {
        scrollEl.scrollTop = currentRow.offsetTop - 8
      }
    })
    return () => cancelAnimationFrame(raf)
  }, [mapData?.currentLocationId, discovered.length])

  return (
    <div className="neq-map-tab">
      <div className="neq-map-toolbar">
        <span className="neq-map-zoom">{zoomPct}%</span>
        <button type="button" className="neq-map-btn" disabled={!mapData} onClick={handleReset}>⟲ reset</button>
        <button type="button" className="neq-map-btn" disabled={!mapData} onClick={handleFull}>▭ full</button>
      </div>
      <div className={`neq-map-stage-wrap${mapData ? '' : ' neq-map-stage-wrap--empty'}`}>
        <div ref={stageRef} className="neq-map-stage" />
        {!mapData && <div className="neq-map-placeholder">The map is blank&hellip;</div>}
      </div>
      {mapData && (
        <div className="neq-notes-wrap">
          <div className="neq-notes-card">
            <div className="neq-notes-header">
              <span className="neq-notes-title">Explorer&rsquo;s Notes</span>
              <span className="neq-notes-progress">
                {discovered.length} of {totalCount} places discovered
              </span>
            </div>
            <div className="neq-notes-scroll" ref={notesScrollRef}>
              <div className="neq-notes-list">
                {discovered.map((room) => {
                  const isCurrent = room.id === mapData.currentLocationId
                  const classes = ['neq-notes-row']
                  if (isCurrent) classes.push('is-current')
                  if (focusedRowId === room.id) classes.push('is-focused')
                  return (
                    <button
                      key={room.id}
                      type="button"
                      ref={isCurrent ? currentRowRef : undefined}
                      className={classes.join(' ')}
                      onClick={() => handleRowClick(room.id)}
                    >
                      <span className="neq-notes-row-main">
                        {isCurrent && <span className="neq-notes-dot" aria-hidden="true" />}
                        <span className="neq-notes-row-name">{room.name}</span>
                      </span>
                      <span className="neq-notes-row-type">{room.type ?? ''}</span>
                    </button>
                  )
                })}
              </div>
              {undiscoveredCount > 0 && (
                <div className="neq-notes-undiscovered">
                  &hellip;and {undiscoveredCount} {undiscoveredCount === 1 ? 'place' : 'places'} yet undiscovered.
                </div>
              )}
              {mapData.area.areaDescription && (
                <>
                  <hr className="neq-notes-excerpt-rule" />
                  <div className="neq-notes-excerpt">{mapData.area.areaDescription}</div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
