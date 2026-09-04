/**
 * Explorer's Notes card: the discovered-rooms list rendered beside (rail) or
 * inside (modal) the map. Extracted from MapTab so the full-screen MapModal
 * can render the same card without duplicating the list, the discovered/
 * undiscovered counts, or the current-row auto-scroll behaviour.
 *
 * Spoiler safety is inherited from the payload, not re-derived here: the
 * server only names rooms it has revealed, so filtering on `name` is the
 * whole of the discovered set (see types/map.ts).
 */
import { useEffect, useMemo, useRef } from 'react'
import type { MapDataPayload, MapRoom } from '../../types/map'

/** A discovered room: one that has been revealed and so carries a name (see MapRoom's SECURITY NOTE cross-reference in types/map.ts). */
type DiscoveredRoom = MapRoom & { name: string }

export interface ExplorerNotesProps {
  mapData: MapDataPayload
  focusedRowId: string | null
  onRowClick: (roomId: string) => void
  /**
   * Which surface the card is rendered on. This is a LAYOUT switch only (it
   * picks the `neq-notes-wrap--rail` / `--modal` class); the content is
   * identical in both. In particular the area-description excerpt renders in
   * both variants by design (controller Ruling 8) -- the modal is a bigger
   * look at the same notes, not a reduced one.
   */
  variant: 'rail' | 'modal'
}

export function ExplorerNotes({ mapData, focusedRowId, onRowClick, variant }: ExplorerNotesProps) {
  const notesScrollRef = useRef<HTMLDivElement>(null)
  const currentRowRef = useRef<HTMLButtonElement>(null)

  // Discovered rooms are simply the ones the server chose to name (see
  // types/map.ts -- unrevealed rooms never carry name/type), in id order so
  // the list doesn't reshuffle as new rooms get revealed out of discovery
  // order.
  const discovered = useMemo<DiscoveredRoom[]>(
    () =>
      mapData.map.rooms
        .filter((r): r is DiscoveredRoom => Boolean(r.name))
        .sort((a, b) => a.id.localeCompare(b.id)),
    [mapData],
  )
  const totalCount = mapData.map.rooms.length
  // Prefer the server-computed undiscoveredCount (counts real rooms not yet
  // revealed, independent of name leakage). Fall back to
  // totalCount - discovered.length for older payloads/fixtures that predate
  // it, so the header "N of M" and this line still sum to M, matching the
  // approved mockup, even if a revealed room ever arrives unnamed.
  const undiscoveredCount = mapData.undiscoveredCount ?? (totalCount - discovered.length)

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
  }, [mapData.currentLocationId, discovered.length])

  return (
    <div className={`neq-notes-wrap neq-notes-wrap--${variant}`}>
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
                  onClick={() => onRowClick(room.id)}
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
  )
}
