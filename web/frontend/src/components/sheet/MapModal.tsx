/**
 * Full-screen map (plan Task 5): the rail's fog-of-war map and Explorer's
 * Notes, side by side at a size you can actually read.
 *
 * This renders a SECOND, independent mapper instance rather than moving the
 * rail's -- createMap owns its container's innerHTML, so one handle can't be
 * re-parented, and the two views want different label scales anyway. It
 * therefore keeps its own handle, pan/zoom wiring and zoom readout, and
 * deliberately does NOT touch `mapTabCache`: the modal is a transient look
 * around, not a change to the view the rail restores on remount.
 *
 * It portals to document.body so that marking the app root `inert` (to keep
 * the background out of the tab order while the dialog is open) can't
 * disable the dialog itself.
 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { createMap, type MapperHandle } from 'mapper-lib'
import type { MapTheme } from '../../stores'
import type { MapDataPayload } from '../../types/map'
import { DialogShell } from '../dialogs/DialogShell'
import { ExplorerNotes } from './ExplorerNotes'
import {
  FULL_VB,
  applyCurrentMarker,
  computeAutoFitViewBox,
  focusRoom,
  setViewBox,
  structuralKey,
  wirePanZoom,
  zoomPercent,
  type ViewBox,
} from './useMapPanZoom'

export interface MapModalProps {
  mapData: MapDataPayload
  theme: MapTheme
  onClose: () => void
}

export function MapModal({ mapData, theme, onClose }: MapModalProps) {
  const stageRef = useRef<HTMLDivElement>(null)
  const handleRef = useRef<MapperHandle | null>(null)
  const keyRef = useRef('')
  const panZoomCleanupRef = useRef<(() => void) | null>(null)
  const [zoomPct, setZoomPct] = useState(100)
  const [focusedRowId, setFocusedRowId] = useState<string | null>(null)

  // Same spoiler guard as the rail: never mark a room the payload hasn't
  // revealed, or the marker would leak the party's position through fog. The
  // legend pill below is gated on the same value, so it never explains a
  // marker that isn't drawn.
  const currentIsRevealed =
    mapData.currentLocationId !== null && mapData.revealed.includes(mapData.currentLocationId)

  function applyMarker(handle: MapperHandle) {
    applyCurrentMarker(handle.svg, currentIsRevealed ? mapData.currentLocationId : null)
  }

  // DialogShell owns nested inertness, focus and scroll locking.

  useEffect(() => {
    const el = stageRef.current
    if (!el) return

    // The palette is baked into the rendered SVG by createMap, so a theme
    // change is a rebuild trigger just like a structural one.
    const key = structuralKey(mapData) + '|' + theme
    // Rebuild only when the map's structure or palette actually changed (or
    // there's no live handle to reuse). `mapData` is a fresh object on every
    // socket refresh, so keying off its identity would tear the map down and
    // snap back to auto-fit mid-look, throwing away the user's pan/zoom.
    if (key !== keyRef.current || !handleRef.current) {
      handleRef.current?.destroy()
      const handle = createMap(el, mapData.map, mapData.area, {
        uid: 'neqmapmodal',
        fontCss: false,
        quiet: true,
        labelScale: 1.4,
        palette: theme,
        // The modal opens onto an already-explored map: replay the reveal set
        // instantly rather than re-running the discovery animation.
        instant: true,
      })
      handleRef.current = handle
      keyRef.current = key
      // A fresh SVG starts at mapper-lib's full-map viewBox, so auto-fit is
      // the right view here (unlike the refresh path below, which must leave
      // whatever the user is looking at alone).
      handle.setRevealed(mapData.revealed)
      applyMarker(handle)
      const fit = computeAutoFitViewBox(handle.svg, mapData.revealed)
      setViewBox(handle.svg, fit)
      setZoomPct(zoomPercent(fit))
    } else {
      // Same map, new payload: fold in the server's revealed set and move the
      // marker in place. The instance is `instant`, so setRevealed applies
      // without animation; the viewBox and zoom% are deliberately untouched.
      const handle = handleRef.current
      handle.setRevealed(mapData.revealed)
      applyMarker(handle)
    }

    // Wired once against a getter, so it survives the rebuilds above and is
    // torn down exactly once, by the unmount effect below.
    if (!panZoomCleanupRef.current) {
      panZoomCleanupRef.current = wirePanZoom(
        el,
        () => handleRef.current?.svg ?? null,
        (vb: ViewBox) => setZoomPct(zoomPercent(vb)),
      )
    }
  }, [mapData, theme])

  // StrictMode-safe teardown: removes the pan/zoom listeners and destroys the
  // rendered SVG once, on unmount. The effect above then rebuilds on a
  // remount because `handleRef.current` is null.
  useEffect(
    () => () => {
      panZoomCleanupRef.current?.()
      panZoomCleanupRef.current = null
      handleRef.current?.destroy()
      handleRef.current = null
    },
    [],
  )

  function view(vb: ViewBox) {
    const svg = handleRef.current?.svg
    if (!svg) return
    setViewBox(svg, vb)
    setZoomPct(zoomPercent(vb))
  }

  function handleFit() {
    const svg = handleRef.current?.svg
    if (svg) view(computeAutoFitViewBox(svg, mapData.revealed))
  }

  function handleRowClick(roomId: string) {
    setFocusedRowId(roomId)
    const svg = handleRef.current?.svg
    if (svg) focusRoom(svg, roomId, (vb) => setZoomPct(zoomPercent(vb)))
  }

  return createPortal(
    <DialogShell title={mapData.areaName} onClose={onClose} maxWidth="min(1400px, 96vw)">
      <div className="neq-map-modal" data-map-theme={theme}>
        <div className="neq-map-modal-main">
          <div className="neq-map-toolbar">
            <span className="neq-map-zoom">{zoomPct}%</span>
            <button type="button" className="neq-map-btn" onClick={handleFit}>⊙ fit</button>
            <button type="button" className="neq-map-btn" onClick={() => view(FULL_VB)}>▭ whole</button>
            <button type="button" className="neq-map-btn" onClick={onClose}>✕ close</button>
          </div>
          <div className="neq-map-stage-wrap">
            <div ref={stageRef} className="neq-map-stage" />
            {currentIsRevealed && (
              <span className="neq-map-here-pill">
                <i aria-hidden="true" />
                You are here
              </span>
            )}
          </div>
        </div>
        <ExplorerNotes
          mapData={mapData}
          focusedRowId={focusedRowId}
          onRowClick={handleRowClick}
          variant="modal"
        />
      </div>
    </DialogShell>,
    document.body,
  )
}
