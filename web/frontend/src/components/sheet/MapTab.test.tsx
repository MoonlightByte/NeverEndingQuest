// @vitest-environment jsdom
import { StrictMode } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MapperHandle } from 'mapper-lib'

const { createMapMock } = vi.hoisted(() => ({ createMapMock: vi.fn() }))

vi.mock('mapper-lib', () => ({ createMap: createMapMock }))

// Spies on computeAutoFitViewBox (real implementation underneath) so the F4
// regression test can assert the reset handler recomputes against the
// *current* mapData.revealed instead of trusting a possibly-stale ref,
// without needing to hand-roll real SVG bbox geometry in every test. Also
// spies on wirePanZoom so N1 tests can grab its onChange callback and
// simulate a real wheel-zoom/drag-pan without needing jsdom SVG CTM support.
vi.mock('./useMapPanZoom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./useMapPanZoom')>()
  return {
    ...actual,
    computeAutoFitViewBox: vi.fn(actual.computeAutoFitViewBox),
    wirePanZoom: vi.fn(actual.wirePanZoom),
    focusRoom: vi.fn(actual.focusRoom),
  }
})

import { useWorld } from '../../stores'
import { useSettings } from '../../stores/settings'
import type { MapDataPayload } from '../../types/map'
import { computeAutoFitViewBox, focusRoom, resetMapTabCacheForTests, wirePanZoom, type ViewBox } from './useMapPanZoom'
import { MapTab } from './MapTab'

const worldInitial = useWorld.getState()
const computeAutoFitViewBoxMock = vi.mocked(computeAutoFitViewBox)
const wirePanZoomMock = vi.mocked(wirePanZoom)
const focusRoomMock = vi.mocked(focusRoom)

/** Grabs the onChange callback MapTab passed to the most recent wirePanZoom() call, so a test can simulate a real wheel-zoom/drag-pan without jsdom SVG CTM support. */
function latestPanZoomOnChange(): (vb: ViewBox) => void {
  const call = wirePanZoomMock.mock.calls.at(-1)
  if (!call) throw new Error('wirePanZoom was never called')
  return call[2]
}

function makeSvg(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement
  document.body.append(svg)
  return svg
}

function makeHandle(revealed: string[]): MapperHandle {
  const svg = makeSvg()
  let state = [...revealed]
  return {
    svg,
    graph: { mapId: 'HH001', mapName: "Harrow's Hollow", rooms: new Map(), edges: [], warnings: [] },
    reveal: vi.fn((id: string) => {
      if (!state.includes(id)) state.push(id)
    }),
    revealAll: vi.fn(),
    setRevealed: vi.fn((ids: string[]) => {
      state = [...ids]
    }),
    revealed: vi.fn(() => state),
    dispose: vi.fn(),
    destroy: vi.fn(),
  }
}

function payload(overrides: Partial<MapDataPayload> = {}): MapDataPayload {
  return {
    areaId: 'HH001',
    areaName: "Harrow's Hollow",
    map: {
      mapId: 'HH001',
      mapName: "Harrow's Hollow",
      rooms: [
        { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
        { id: 'A02', coordinates: '1,0', connections: ['A01'], name: 'East Gate', type: 'gate' },
      ],
    },
    area: { areaType: 'town', terrain: null, climate: null, areaDescription: null },
    revealed: ['A01'],
    currentLocationId: 'A01',
    ...overrides,
  }
}

beforeEach(() => {
  cleanup()
  createMapMock.mockReset()
  computeAutoFitViewBoxMock.mockClear()
  wirePanZoomMock.mockClear()
  focusRoomMock.mockClear()
  useWorld.setState(worldInitial, true)
  useSettings.getState().setMapTheme('day')
  resetMapTabCacheForTests()
})

afterEach(() => {
  document.body.replaceChildren()
})

describe('MapTab', () => {
  it('shows the empty-state placeholder with no mapData', () => {
    const { container } = render(<MapTab />)
    expect(container.textContent).toContain('The map is blank')
    expect(createMapMock).not.toHaveBeenCalled()
  })

  it('F5: keeps the empty-state placeholder outside the mapper-managed stage element', () => {
    const { container } = render(<MapTab />)
    const stage = container.querySelector('.neq-map-stage')
    const placeholder = container.querySelector('.neq-map-placeholder')
    expect(stage).not.toBeNull()
    expect(placeholder).not.toBeNull()
    expect(stage?.contains(placeholder)).toBe(false)
  })

  // `:not([aria-pressed])` excludes the day/night toggle, which is a display
  // preference rather than a map-view action and so stays enabled even with
  // no map loaded; the fit/whole/expand buttons are the view actions.
  const viewButtons = '.neq-map-btn:not([aria-pressed])'

  it('disables the toolbar buttons until a map exists', () => {
    const { container, rerender } = render(<MapTab />)
    for (const b of container.querySelectorAll<HTMLButtonElement>(viewButtons)) expect(b.disabled).toBe(true)

    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)
    act(() => {
      useWorld.setState({ mapData: payload() })
    })
    rerender(<MapTab />)
    for (const b of container.querySelectorAll<HTMLButtonElement>(viewButtons)) expect(b.disabled).toBe(false)
  })

  it('creates the map once per structural change, applies setRevealed before reveal(), and matches the createMap call shape', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload() })
    })
    render(<MapTab />)

    expect(createMapMock).toHaveBeenCalledTimes(1)
    expect(createMapMock).toHaveBeenCalledWith(
      expect.anything(),
      payload().map,
      payload().area,
      expect.objectContaining({ uid: 'neqmap', fontCss: false, quiet: true, labelScale: 1.6 }),
    )
    // setRevealed(prev ∩ next) with an empty prior handle, then reveal() for
    // the delta -- A01 arrives via the animated reveal() path, not setRevealed.
    expect(handle.setRevealed).toHaveBeenCalledWith([])
    expect(handle.reveal).toHaveBeenCalledWith('A01')
    // Ordering matters: replaying prior state must land before animating the
    // delta, or the delta's reveal() could be clobbered by a later setRevealed.
    const setRevealedOrder = vi.mocked(handle.setRevealed).mock.invocationCallOrder[0]
    const revealOrder = vi.mocked(handle.reveal).mock.invocationCallOrder[0]
    expect(setRevealedOrder).toBeLessThan(revealOrder)
  })

  it('does not recreate the map for a same-structure re-render, and animates only newly revealed rooms', () => {
    const handle = makeHandle(['A01'])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    const { rerender } = render(<MapTab />)
    expect(createMapMock).toHaveBeenCalledTimes(1)
    vi.mocked(handle.reveal).mockClear()

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01', 'A02'] }) })
    })
    rerender(<MapTab />)

    // Same structural key (both rooms already carry full name/type in this
    // fixture) -- no rebuild, just an animated reveal of the delta.
    expect(createMapMock).toHaveBeenCalledTimes(1)
    expect(handle.reveal).toHaveBeenCalledWith('A02')
    expect(handle.reveal).not.toHaveBeenCalledWith('A01')
  })

  it('a same-area structural change (e.g. a redacted room gaining name+type) carries over the non-empty intersection via setRevealed', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    const redactedA02 = payload({
      map: {
        mapId: 'HH001',
        mapName: "Harrow's Hollow",
        rooms: [
          { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
          { id: 'A02', coordinates: '1,0', connections: ['A01'] }, // redacted: no name/type yet
        ],
      },
      revealed: ['A01'],
    })
    act(() => {
      useWorld.setState({ mapData: redactedA02 })
    })
    const { rerender } = render(<MapTab />)
    expect(createMapMock).toHaveBeenCalledTimes(1)
    vi.mocked(handle.setRevealed).mockClear()

    // A02 is now revealed and its name/type populate -- a structural change
    // within the SAME area.
    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01', 'A02'] }) })
    })
    rerender(<MapTab />)

    expect(createMapMock).toHaveBeenCalledTimes(2)
    // Non-tautological: this must be a real, non-empty intersection (['A01']),
    // not the trivially-true "called with an array" or the empty-prev case
    // already covered by the area-change test below.
    expect(handle.setRevealed).toHaveBeenCalledWith(['A01'])
  })

  it('an area change discards the prior handle\'s reveal state via setRevealed([])', () => {
    const handleA = makeHandle(['A01'])
    createMapMock.mockReturnValueOnce(handleA)

    act(() => {
      useWorld.setState({ mapData: payload({ areaId: 'HH001', revealed: ['A01'] }) })
    })
    const { rerender } = render(<MapTab />)
    expect(createMapMock).toHaveBeenCalledTimes(1)

    const handleB = makeHandle([])
    createMapMock.mockReturnValueOnce(handleB)
    act(() => {
      useWorld.setState({
        mapData: payload({
          areaId: 'B02',
          areaName: 'Somewhere Else',
          map: { mapId: 'B02', mapName: 'Somewhere Else', rooms: [{ id: 'B01', coordinates: '0,0', connections: [], name: 'Cave Mouth', type: 'cave' }] },
          revealed: ['B01'],
          currentLocationId: 'B01',
        }),
      })
    })
    rerender(<MapTab />)

    expect(createMapMock).toHaveBeenCalledTimes(2)
    expect(handleB.setRevealed).toHaveBeenCalledWith([])
  })

  it('F2: shrinks via setRevealed when the server-revealed set drops an id (e.g. a reset), not diffReveals', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01', 'A02'] }) })
    })
    const { rerender } = render(<MapTab />)
    expect(handle.revealed()).toEqual(['A01', 'A02'])
    vi.mocked(handle.setRevealed).mockClear()
    vi.mocked(handle.reveal).mockClear()

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    rerender(<MapTab />)

    expect(handle.setRevealed).toHaveBeenCalledWith(['A01'])
    expect(handle.reveal).not.toHaveBeenCalled()
    expect(handle.revealed()).toEqual(['A01'])
  })

  it('F4: reset recomputes auto-fit fresh from the current mapData.revealed, not a stale cached viewBox', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    const { rerender } = render(<MapTab />)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01', 'A02'] }) })
    })
    rerender(<MapTab />)
    computeAutoFitViewBoxMock.mockClear()

    act(() => {
      fireEvent.click(screen.getByText('⊙ fit'))
    })

    expect(computeAutoFitViewBoxMock).toHaveBeenCalledWith(handle.svg, ['A01', 'A02'])
  })

  it('F5: destroys the handle and shows the placeholder again when mapData goes back to null', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload() })
    })
    const { rerender, container } = render(<MapTab />)
    expect(createMapMock).toHaveBeenCalledTimes(1)

    act(() => {
      useWorld.setState({ mapData: null })
    })
    rerender(<MapTab />)

    expect(handle.destroy).toHaveBeenCalledTimes(1)
    expect(container.textContent).toContain('The map is blank')
  })

  it('destroys the handle on unmount', () => {
    const handle = makeHandle([])
    createMapMock.mockReturnValue(handle)

    act(() => {
      useWorld.setState({ mapData: payload() })
    })
    const { unmount } = render(<MapTab />)
    unmount()

    expect(handle.destroy).toHaveBeenCalledTimes(1)
  })

  it('F3: a remount within the same area reuses the cached revealed snapshot via setRevealed instead of re-animating', () => {
    const handle1 = makeHandle([])
    createMapMock.mockReturnValueOnce(handle1)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    const { unmount } = render(<MapTab />)
    expect(handle1.reveal).toHaveBeenCalledWith('A01')

    unmount()
    expect(handle1.destroy).toHaveBeenCalledTimes(1)

    const handle2 = makeHandle([])
    createMapMock.mockReturnValueOnce(handle2)
    render(<MapTab />)

    expect(createMapMock).toHaveBeenCalledTimes(2)
    // The remount's rebuild replays the cached revealed set instantly via
    // setRevealed, rather than animating A01 in again via reveal().
    expect(handle2.setRevealed).toHaveBeenCalledWith(['A01'])
    expect(handle2.reveal).not.toHaveBeenCalledWith('A01')
  })

  it('N1(a): a same-area remount while userTouched restores the last live view (not just the default full-map viewBox the fresh SVG starts at)', () => {
    const handle1 = makeHandle([])
    createMapMock.mockReturnValueOnce(handle1)

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    const { unmount } = render(<MapTab />)

    // Simulate a real wheel-zoom/drag-pan landing on a distinctive,
    // non-default viewBox -- not the Full button, which would itself set
    // the default full-map box and couldn't prove restoration happened.
    const touchedVb: ViewBox = { x: 120, y: 90, w: 480, h: 360 }
    act(() => {
      latestPanZoomOnChange()(touchedVb)
    })
    expect(screen.getByText('250%')).toBeTruthy() // round(1200/480*100)

    unmount()
    expect(handle1.destroy).toHaveBeenCalledTimes(1)

    const handle2 = makeHandle([])
    createMapMock.mockReturnValueOnce(handle2)
    render(<MapTab />)

    // The fresh SVG the new createMap() call produces starts at mapper-lib's
    // own default viewBox; MapTab must overwrite it with the cached touched
    // view rather than leaving it there or re-running auto-fit.
    expect(handle2.svg.getAttribute('viewBox')).toBe('120 90 480 360')
    expect(screen.getByText('250%')).toBeTruthy()
  })

  it("N1(b): moving areas clears cache.userTouched so a later remount in the new area still auto-fits, instead of inheriting the old area's touched flag", () => {
    const handleA = makeHandle([])
    createMapMock.mockReturnValueOnce(handleA)

    act(() => {
      useWorld.setState({ mapData: payload({ areaId: 'HH001', revealed: ['A01'] }) })
    })
    const { unmount } = render(<MapTab />)

    // Touch the view while in HH001, then leave the tab (unmount) without
    // ever clearing that touch -- this is the exact bug scenario: "pan in
    // area A, then move to area B."
    act(() => {
      latestPanZoomOnChange()({ x: 50, y: 50, w: 300, h: 225 })
    })
    unmount()
    expect(handleA.destroy).toHaveBeenCalledTimes(1)

    // The party moves to a new area entirely (server-driven, no MapTab
    // mounted to observe it happening).
    act(() => {
      useWorld.setState({
        mapData: payload({
          areaId: 'B02',
          areaName: 'Somewhere Else',
          map: {
            mapId: 'B02',
            mapName: 'Somewhere Else',
            rooms: [{ id: 'B01', coordinates: '0,0', connections: [], name: 'Cave Mouth', type: 'cave' }],
          },
          revealed: ['B01'],
          currentLocationId: 'B01',
        }),
      })
    })

    // Before the N1(b) fix, cache.userTouched was still `true` from the
    // HH001 pan above -- seeding this fresh instance's userTouchedRef with a
    // stale `true` and permanently suppressing auto-fit in the new area.
    const handleB = makeHandle([])
    createMapMock.mockReturnValueOnce(handleB)
    render(<MapTab />)

    expect(computeAutoFitViewBoxMock).toHaveBeenCalledWith(handleB.svg, ['B01'])
    expect(handleB.svg.getAttribute('viewBox')).not.toBe('50 50 300 225')
  })

  it('is StrictMode-safe: the discarded first-pass handle is destroyed and the survivor keeps the reveal state via setRevealed, not a re-animation', () => {
    const handles: MapperHandle[] = []
    createMapMock.mockImplementation(() => {
      const h = makeHandle([])
      handles.push(h)
      return h
    })

    act(() => {
      useWorld.setState({ mapData: payload({ revealed: ['A01'] }) })
    })
    render(
      <StrictMode>
        <MapTab />
      </StrictMode>,
    )

    // StrictMode double-invokes the mount effect (setup -> cleanup -> setup)
    // in dev to surface non-idempotent effects.
    expect(createMapMock).toHaveBeenCalledTimes(2)
    expect(handles[0].destroy).toHaveBeenCalledTimes(1)
    expect(handles[1].destroy).not.toHaveBeenCalled()
    expect(handles[1].setRevealed).toHaveBeenCalledWith(['A01'])
    expect(handles[1].reveal).not.toHaveBeenCalledWith('A01')
  })

  describe('React#7: marker only if currentLocationId is in revealed', () => {
    /** Appends a real [data-room] group, with the renderer's data-anchor, to `svg` so applyCurrentMarker has something to anchor on. */
    function appendRoomGroup(svg: SVGSVGElement, id: string): void {
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      g.setAttribute('data-room', id)
      g.setAttribute('data-anchor', '10,10')
      svg.append(g)
    }

    it('draws the pulse marker when currentLocationId is in revealed', () => {
      const handle = makeHandle(['A01'])
      appendRoomGroup(handle.svg, 'A01')
      createMapMock.mockReturnValue(handle)

      act(() => {
        useWorld.setState({ mapData: payload({ revealed: ['A01'], currentLocationId: 'A01' }) })
      })
      render(<MapTab />)

      expect(handle.svg.querySelector('.neq-map-here-marker')).not.toBeNull()
    })

    it('omits the pulse marker when currentLocationId is NOT in revealed (defensive: prevents a position leak on a fogged room)', () => {
      const handle = makeHandle(['A01'])
      appendRoomGroup(handle.svg, 'A01')
      appendRoomGroup(handle.svg, 'A02')
      createMapMock.mockReturnValue(handle)

      act(() => {
        // currentLocationId points at a room the server invariant says should
        // always be in `revealed` -- simulate that invariant slipping.
        useWorld.setState({ mapData: payload({ revealed: ['A01'], currentLocationId: 'A02' }) })
      })
      render(<MapTab />)

      expect(handle.svg.querySelector('.neq-map-here-marker')).toBeNull()
      expect(handle.svg.querySelector('.neq-map-here')).toBeNull()
    })
  })

  describe("Explorer's Notes", () => {
    function notesPayload(overrides: Partial<MapDataPayload> = {}): MapDataPayload {
      return payload({
        map: {
          mapId: 'HH001',
          mapName: "Harrow's Hollow",
          rooms: [
            { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
            { id: 'A02', coordinates: '1,0', connections: ['A01', 'A03'], name: 'Town Square', type: 'square' },
            // Not yet revealed -- no name/type, per the SECURITY NOTE in
            // types/map.ts -- must never appear in the discovered list.
            { id: 'A03', coordinates: '2,0', connections: ['A02'] },
          ],
        },
        revealed: ['A01', 'A02'],
        currentLocationId: 'A02',
        ...overrides,
      })
    }

    it('lists only discovered (named) rooms in id order, with the correct progress and undiscovered counts', () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)

      act(() => {
        useWorld.setState({ mapData: notesPayload() })
      })
      const { container } = render(<MapTab />)

      const rows = container.querySelectorAll('.neq-notes-row')
      // Exactly the two named rooms -- the redacted A03 never appears, even
      // though it's present in map.rooms and counted toward the total.
      expect(rows).toHaveLength(2)
      expect(rows[0].querySelector('.neq-notes-row-name')?.textContent).toBe('General Store')
      expect(rows[1].querySelector('.neq-notes-row-name')?.textContent).toBe('Town Square')
      expect(rows[0].querySelector('.neq-notes-row-type')?.textContent).toBe('shop')
      expect(container.querySelector('.neq-notes-progress')?.textContent).toBe('2 of 3 places discovered')
      expect(container.querySelector('.neq-notes-undiscovered')?.textContent).toBe('…and 1 place yet undiscovered.')
    })

    it('marks the current-location row with is-current and a pulse dot, and no other row', () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)

      act(() => {
        useWorld.setState({ mapData: notesPayload({ currentLocationId: 'A02' }) })
      })
      const { container } = render(<MapTab />)

      const rows = [...container.querySelectorAll('.neq-notes-row')]
      const current = rows.find((r) => r.classList.contains('is-current'))
      expect(current?.querySelector('.neq-notes-row-name')?.textContent).toBe('Town Square')
      expect(current?.querySelector('.neq-notes-dot')).not.toBeNull()
      const others = rows.filter((r) => r !== current)
      expect(others.length).toBeGreaterThan(0)
      for (const r of others) {
        expect(r.classList.contains('is-current')).toBe(false)
        expect(r.querySelector('.neq-notes-dot')).toBeNull()
      }
    })

    it('omits the undiscovered line once every room is revealed', () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)

      act(() => {
        useWorld.setState({
          mapData: notesPayload({
            map: {
              mapId: 'HH001',
              mapName: "Harrow's Hollow",
              rooms: [
                { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
                { id: 'A02', coordinates: '1,0', connections: ['A01'], name: 'Town Square', type: 'square' },
              ],
            },
            revealed: ['A01', 'A02'],
          }),
        })
      })
      const { container } = render(<MapTab />)

      expect(container.querySelector('.neq-notes-undiscovered')).toBeNull()
    })

    it('clicking a discovered row calls focusRoom with the live svg and that room id, and highlights the row', () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)

      act(() => {
        useWorld.setState({ mapData: notesPayload() })
      })
      const { container } = render(<MapTab />)

      const rows = [...container.querySelectorAll<HTMLButtonElement>('.neq-notes-row')]
      const storeRow = rows.find((r) => r.querySelector('.neq-notes-row-name')?.textContent === 'General Store')
      expect(storeRow).toBeTruthy()

      act(() => {
        fireEvent.click(storeRow!)
      })

      expect(focusRoomMock).toHaveBeenCalledWith(handle.svg, 'A01', expect.any(Function))
      expect(storeRow?.classList.contains('is-focused')).toBe(true)
    })

    it('a row-click focus counts as a user-chosen view: it persists across a same-area remount (D1 semantics)', () => {
      const handle1 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle1)

      act(() => {
        useWorld.setState({ mapData: notesPayload() })
      })
      const { container, unmount } = render(<MapTab />)

      const row = container.querySelector<HTMLButtonElement>('.neq-notes-row')!
      act(() => {
        fireEvent.click(row)
      })
      // Drive the real focus viewBox through the onChange the click handed to
      // focusRoom -- the same markTouched path pan/zoom and Full use.
      const onChange = focusRoomMock.mock.calls.at(-1)![2] as (vb: ViewBox) => void
      const focusVb: ViewBox = { x: 200, y: 150, w: 400, h: 300 }
      act(() => {
        onChange(focusVb)
      })
      expect(screen.getByText('300%')).toBeTruthy() // round(1200/400*100)

      unmount()
      const handle2 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle2)
      render(<MapTab />)

      // The remount must restore the clicked-focus view, not auto-fit.
      expect(handle2.svg.getAttribute('viewBox')).toBe('200 150 400 300')
      expect(screen.getByText('300%')).toBeTruthy()
    })

    it('a structural change (area move) clears the row-focus highlight', () => {
      const handle1 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle1)
      act(() => {
        useWorld.setState({ mapData: notesPayload() })
      })
      const { container } = render(<MapTab />)
      const row = container.querySelector<HTMLButtonElement>('.neq-notes-row')!
      act(() => {
        fireEvent.click(row)
      })
      expect(container.querySelector('.is-focused')).toBeTruthy()

      const handle2 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle2)
      act(() => {
        // New area reusing the SAME room ids -- the highlight must not carry.
        useWorld.setState({ mapData: notesPayload({ areaId: 'ZZ001' }) })
      })
      expect(container.querySelector('.is-focused')).toBeNull()
    })

    it('F5: a same-area structural change (e.g. a new room discovered) keeps the row-focus highlight', () => {
      const handle1 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle1)
      act(() => {
        useWorld.setState({ mapData: notesPayload() })
      })
      const { container } = render(<MapTab />)
      const row = container.querySelector<HTMLButtonElement>('.neq-notes-row')!
      act(() => {
        fireEvent.click(row)
      })
      expect(container.querySelector('.is-focused')).toBeTruthy()

      const handle2 = makeHandle([])
      createMapMock.mockReturnValueOnce(handle2)
      act(() => {
        // Same area (HH001), but A03 is now revealed and named -- a
        // structural change (structuralKey includes name/type) that must NOT
        // drop a still-valid highlight on the unrelated, unchanged A01 row.
        useWorld.setState({
          mapData: notesPayload({
            map: {
              mapId: 'HH001',
              mapName: "Harrow's Hollow",
              rooms: [
                { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
                { id: 'A02', coordinates: '1,0', connections: ['A01', 'A03'], name: 'Town Square', type: 'square' },
                { id: 'A03', coordinates: '2,0', connections: ['A02'], name: 'Blacksmith', type: 'shop' },
              ],
            },
            revealed: ['A01', 'A02', 'A03'],
          }),
        })
      })
      expect(container.querySelector('.is-focused')).toBeTruthy()
    })
  })

  describe('Explorer\'s Notes auto-scroll (F4: bidirectional)', () => {
    function notesPayloadWide(overrides: Partial<MapDataPayload> = {}): MapDataPayload {
      return payload({
        map: {
          mapId: 'HH001',
          mapName: "Harrow's Hollow",
          rooms: [
            { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
            { id: 'A02', coordinates: '1,0', connections: ['A01'], name: 'Town Square', type: 'square' },
          ],
        },
        revealed: ['A01', 'A02'],
        currentLocationId: 'A01',
        ...overrides,
      })
    }

    it('scrolls DOWN to reveal the current row when it is below the fold', async () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)
      act(() => {
        useWorld.setState({ mapData: notesPayloadWide() })
      })
      const { container } = render(<MapTab />)

      const scrollEl = container.querySelector<HTMLDivElement>('.neq-notes-scroll')!
      const currentRow = container.querySelector<HTMLButtonElement>('.neq-notes-row.is-current')!
      Object.defineProperty(scrollEl, 'clientHeight', { value: 200, configurable: true })
      Object.defineProperty(scrollEl, 'scrollTop', { value: 0, writable: true, configurable: true })
      Object.defineProperty(currentRow, 'offsetTop', { value: 1000, configurable: true })
      Object.defineProperty(currentRow, 'offsetHeight', { value: 30, configurable: true })

      await act(async () => {
        await new Promise((resolve) => requestAnimationFrame(resolve))
      })

      expect(scrollEl.scrollTop).toBe(1000 + 30 - 200 + 8)
    })

    it('scrolls UP to reveal the current row when it is above the fold (regression: was down-only)', async () => {
      const handle = makeHandle([])
      createMapMock.mockReturnValue(handle)
      act(() => {
        useWorld.setState({ mapData: notesPayloadWide() })
      })
      const { container } = render(<MapTab />)

      const scrollEl = container.querySelector<HTMLDivElement>('.neq-notes-scroll')!
      const currentRow = container.querySelector<HTMLButtonElement>('.neq-notes-row.is-current')!
      Object.defineProperty(scrollEl, 'clientHeight', { value: 200, configurable: true })
      // Simulate the user having manually scrolled down before relocation.
      Object.defineProperty(scrollEl, 'scrollTop', { value: 500, writable: true, configurable: true })
      Object.defineProperty(currentRow, 'offsetTop', { value: 50, configurable: true })
      Object.defineProperty(currentRow, 'offsetHeight', { value: 30, configurable: true })

      await act(async () => {
        await new Promise((resolve) => requestAnimationFrame(resolve))
      })

      expect(scrollEl.scrollTop).toBe(50 - 8)
    })
  })
})

describe('MapTab day/night theme and toolbar', () => {
  it('passes the persisted palette to createMap and re-creates the map on theme change, restoring reveals instantly', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    useSettings.getState().setMapTheme('day')
    act(() => useWorld.setState({ mapData: payload({ revealed: ['A01', 'A02'] }) }))
    render(<MapTab />)
    expect(createMapMock.mock.calls[0][3]).toMatchObject({ palette: 'day', fontCss: false, quiet: true, labelScale: 1.6 })
    act(() => useSettings.getState().setMapTheme('night'))
    expect(createMapMock).toHaveBeenCalledTimes(2)
    expect(createMapMock.mock.calls[1][3]).toMatchObject({ palette: 'night', instant: true })
    const second = createMapMock.mock.results[1].value as MapperHandle
    expect(second.setRevealed).toHaveBeenCalledWith(['A01', 'A02'])
    expect(screen.getByRole('button', { name: '☾ night' }).getAttribute('aria-pressed')).toBe('true')
    expect(document.querySelector('.neq-map-tab')?.getAttribute('data-map-theme')).toBe('night')
  })

  it('toolbar: fit / whole / expand are labelled and enabled once a map exists', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    act(() => useWorld.setState({ mapData: payload() }))
    render(<MapTab />)
    for (const name of ['⊙ fit', '▭ whole', '⤢ expand']) {
      expect(screen.getByRole<HTMLButtonElement>('button', { name }).disabled).toBe(false)
    }
  })

  it('shows a warning glyph when mapDataError is set or the map area differs from the current location area', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    act(() => useWorld.setState({ mapData: payload(), mapDataError: 'Area data unavailable' }))
    render(<MapTab />)
    expect(screen.getByRole('img', { name: /Area data unavailable/ }).textContent).toBe('⚠')
    act(() =>
      useWorld.setState({
        mapDataError: null,
        location: { currentLocation: 'x', currentArea: 'y', currentLocationId: 'B01', currentAreaId: 'G001', time: '', day: 1, month: '', year: 1 } as never,
      }),
    )
    expect(screen.getByRole('img', { name: /showing HH001/ }).getAttribute('aria-label')).toBe('Map is showing HH001; you are in G001')
  })
})
