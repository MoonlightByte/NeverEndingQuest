// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import type { MapDataPayload } from '../../types/map'
import {
  FULL_VB,
  applyCurrentMarker,
  clampViewBox,
  computeAutoFitViewBox,
  diffReveals,
  focusRoom,
  markerAnchorBBox,
  structuralKey,
  zoomPercent,
} from './useMapPanZoom'

type Bbox = { x: number; y: number; width: number; height: number }

/**
 * jsdom doesn't implement SVGGraphicsElement.getBBox() (throws "not
 * implemented"), so tests that need it stub it directly on each element --
 * same technique computeAutoFitViewBox's own try/catch is defensive against
 * in production.
 */
function fakeRoom(id: string, bbox: Bbox): SVGGraphicsElement {
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'g') as unknown as SVGGraphicsElement
  el.setAttribute('data-room', id)
  ;(el as unknown as { getBBox: () => Bbox }).getBBox = () => bbox
  return el
}

/** A child node (icon/label/decoration group) with a stubbed getBBox, for markerAnchorBBox/applyCurrentMarker tests. */
function fakeChild(tag: string, bbox: Bbox): SVGGraphicsElement {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag) as unknown as SVGGraphicsElement
  ;(el as unknown as { getBBox: () => Bbox }).getBBox = () => bbox
  return el
}

function fakeSvg(rooms: SVGGraphicsElement[]): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement
  for (const r of rooms) svg.append(r)
  return svg
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
        { id: 'A02', coordinates: '1,0', connections: ['A01'] },
      ],
    },
    area: { areaType: 'town', terrain: null, climate: null, areaDescription: null },
    revealed: ['A01'],
    currentLocationId: 'A01',
    ...overrides,
  }
}

describe('structuralKey', () => {
  it('is stable for identical data', () => {
    expect(structuralKey(payload())).toBe(structuralKey(payload()))
  })

  it('changes when a room name changes (e.g. redacted -> revealed)', () => {
    const before = structuralKey(payload())
    const after = structuralKey(
      payload({
        map: {
          mapId: 'HH001',
          mapName: "Harrow's Hollow",
          rooms: [
            { id: 'A01', coordinates: '0,0', connections: ['A02'], name: 'General Store', type: 'shop' },
            { id: 'A02', coordinates: '1,0', connections: ['A01'], name: 'East Gate', type: 'gate' },
          ],
        },
      }),
    )
    expect(after).not.toBe(before)
  })

  it('changes when the area changes', () => {
    expect(structuralKey(payload({ areaId: 'B02' }))).not.toBe(structuralKey(payload()))
  })

  it('is insensitive to connection array order', () => {
    const a = payload({
      map: {
        mapId: 'HH001',
        mapName: "Harrow's Hollow",
        rooms: [{ id: 'A01', coordinates: '0,0', connections: ['A02', 'A03'], name: 'Store', type: 'shop' }],
      },
    })
    const b = payload({
      map: {
        mapId: 'HH001',
        mapName: "Harrow's Hollow",
        rooms: [{ id: 'A01', coordinates: '0,0', connections: ['A03', 'A02'], name: 'Store', type: 'shop' }],
      },
    })
    expect(structuralKey(a)).toBe(structuralKey(b))
  })
})

describe('diffReveals', () => {
  it('returns only ids newly present in next', () => {
    expect(diffReveals(['A01'], ['A01', 'A02', 'A03'])).toEqual(['A02', 'A03'])
  })

  it('returns an empty array when nothing new was revealed', () => {
    expect(diffReveals(['A01', 'A02'], ['A01', 'A02'])).toEqual([])
  })

  it('treats an empty prev as everything being new', () => {
    expect(diffReveals([], ['A01', 'A02'])).toEqual(['A01', 'A02'])
  })
})

describe('computeAutoFitViewBox', () => {
  it('falls back to the full map when none of the revealed ids have a rendered [data-room]', () => {
    const svg = fakeSvg([])
    expect(computeAutoFitViewBox(svg, ['A01'])).toEqual(FULL_VB)
  })

  it('pads the bbox union of the revealed rooms and locks it to 4:3', () => {
    const svg = fakeSvg([
      fakeRoom('A01', { x: 500, y: 400, width: 40, height: 40 }),
      fakeRoom('A02', { x: 600, y: 420, width: 40, height: 40 }),
      // Present in the SVG but NOT in revealedIds -- must not affect the fit.
      fakeRoom('A99', { x: 0, y: 0, width: 10, height: 10 }),
    ])
    const vb = computeAutoFitViewBox(svg, ['A01', 'A02'])

    // Union bbox is x 500..640, y 400..460; padded by 170 on every side that
    // is minX=330, minY=230, maxX=810, maxY=630 -> a 480x400 box. 480/400 =
    // 1.2 < 4/3, so height is the binding dimension and width grows to
    // 400 * 4/3 = 533.33 (not clamped -- inside [400, 1200]).
    expect(vb.h).toBeCloseTo(400, 5)
    expect(vb.w).toBeCloseTo(400 * (4 / 3), 5)
    expect(vb.w / vb.h).toBeCloseTo(4 / 3, 5)
  })

  it('never produces a width below the 400px floor for a single tiny room', () => {
    // The fixed 170px padding on every side already guarantees a width well
    // above MIN_W=400 for any input bbox: a 5x5 room pads out to a 345x345
    // square (170 each side), which is aspect-locked to 345*4/3 = 460 wide.
    // This exercises the floor as a property rather than expecting the
    // clamp branch itself to fire -- with PAD=170 it can't, for any single
    // room, however small.
    const svg = fakeSvg([fakeRoom('A01', { x: 0, y: 0, width: 5, height: 5 })])
    const vb = computeAutoFitViewBox(svg, ['A01'])
    expect(vb.w).toBeGreaterThanOrEqual(400)
    expect(vb.w).toBeCloseTo(345 * (4 / 3), 5)
    expect(vb.h).toBeCloseTo(345, 5)
  })

  it('clamps a huge span down to the 1200px maximum width', () => {
    const svg = fakeSvg([
      fakeRoom('A01', { x: 0, y: 0, width: 10, height: 10 }),
      fakeRoom('A02', { x: 5000, y: 4000, width: 10, height: 10 }),
    ])
    const vb = computeAutoFitViewBox(svg, ['A01', 'A02'])
    expect(vb.w).toBe(1200)
    expect(vb.h).toBeCloseTo(900, 5)
  })

  it('skips a room whose getBBox() throws rather than failing the whole fit', () => {
    const throwing = fakeRoom('A01', { x: 0, y: 0, width: 0, height: 0 })
    ;(throwing as unknown as { getBBox: () => never }).getBBox = () => {
      throw new Error('not implemented')
    }
    const svg = fakeSvg([throwing, fakeRoom('A02', { x: 100, y: 100, width: 20, height: 20 })])
    const vb = computeAutoFitViewBox(svg, ['A01', 'A02'])
    expect(vb).not.toEqual(FULL_VB)
  })

  it('anchors on the room icon, not the (potentially huge, labelScale:2) label text (F1 skew)', () => {
    // Each [data-room] group's own bbox is degenerate; its children are a
    // small icon and, in the second case, a disproportionately large,
    // far-flung label -- the kind a clamped/de-collided labelScale:2 block
    // can produce on a dense map. markerAnchorBBox's outlier filter (used by
    // computeAutoFitViewBox) drops any child whose area is >15x the
    // smallest sibling, so the huge label should be dropped and the fit
    // should come out identical to a room with no label at all -- proving
    // the fit is anchored on the icon and insensitive to label size.
    function roomWithChildren(id: string, ...children: Bbox[]): SVGGraphicsElement {
      const group = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 })
      group.setAttribute('data-room', id)
      group.append(...children.map((b) => fakeChild('g', b)))
      return group
    }

    const iconBox: Bbox = { x: 500, y: 400, width: 20, height: 20 }
    const iconOnlySvg = fakeSvg([roomWithChildren('A01', iconBox)])
    const iconPlusHugeLabelSvg = fakeSvg([
      // Same icon; label is a >15x outlier, offset far away, as a
      // clamped/de-collided labelScale:2 block could be.
      roomWithChildren('A01', iconBox, { x: 200, y: 100, width: 900, height: 300 }),
    ])

    const iconOnlyVb = computeAutoFitViewBox(iconOnlySvg, ['A01'])
    const withHugeLabelVb = computeAutoFitViewBox(iconPlusHugeLabelSvg, ['A01'])

    expect(withHugeLabelVb).toEqual(iconOnlyVb)
  })
})

describe('clampViewBox', () => {
  it('floors width to the 240px pan-zoom minimum and keeps the 4:3 aspect', () => {
    const vb = clampViewBox({ x: 0, y: 0, w: 100, h: 0 })
    expect(vb.w).toBe(240)
    expect(vb.h).toBeCloseTo(180, 5)
  })

  it('caps width to the full 1200px canvas', () => {
    const vb = clampViewBox({ x: 0, y: 0, w: 5000, h: 0 })
    expect(vb.w).toBe(1200)
    expect(vb.h).toBeCloseTo(900, 5)
  })

  it('clamps x/y so the viewBox never pans outside the 1200x900 canvas', () => {
    const vb = clampViewBox({ x: -500, y: 99999, w: 600, h: 0 })
    expect(vb.x).toBe(0)
    expect(vb.y).toBe(FULL_VB.h - vb.h)
  })
})

describe('zoomPercent', () => {
  it('is 100 for the full map', () => {
    expect(zoomPercent(FULL_VB)).toBe(100)
  })

  it('doubles when the viewBox width halves', () => {
    expect(zoomPercent({ x: 0, y: 0, w: 600, h: 450 })).toBe(200)
  })
})

describe('markerAnchorBBox', () => {
  // Backport of the legacy glue fix (web/static/js/mapper-glue.js,
  // markerAnchorBBox) for the same latent bug: the overland renderer nests
  // a room's nearest-neighbor-assigned decorative terrain glyphs inside the
  // SAME <g data-room> as that room's actual icon+label, so unioning the
  // whole group's bbox drags the current-room pulse marker off onto blank
  // parchment. These are the exact real-payload measurements from
  // task-8-report.md's room A02 case: icon 22x19=418px^2, name label
  // 185x22=3989px^2, type tag 30x14=432px^2, decoration group
  // 293x403=118,079px^2 (~282x the icon's area).
  function overlandRoomChildren() {
    return [
      fakeChild('g', { x: 100, y: 100, width: 22, height: 19 }), // icon
      fakeChild('text', { x: 130, y: 95, width: 185, height: 22 }), // name label
      fakeChild('text', { x: 130, y: 118, width: 30, height: 14 }), // type tag
      fakeChild('g', { x: 400, y: 500, width: 293, height: 403 }), // scattered decorations, far away
    ]
  }

  it('anchors to the icon+label cluster, dropping the outlier decoration group', () => {
    const room = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 }) // whole-group bbox is never read directly
    room.setAttribute('data-room', 'A02')
    room.append(...overlandRoomChildren())

    const anchor = markerAnchorBBox([room])

    expect(anchor).not.toBeNull()
    // Union of icon+label+tag only: x 100..315 (icon 100-122, label
    // 130-315, tag 130-160), y 95..132 (label 95-117, icon 100-119, tag
    // 118-132).
    expect(anchor).toEqual({ x: 100, y: 95, width: 215, height: 37 })
    // Center falls on the icon cluster (roughly x~207,y~107), nowhere near
    // the decoration group's footprint (x 400-693, y 500-903) -- this is
    // the ~90px-onto-parchment drift the fix eliminates.
    const cx = anchor!.x + anchor!.width / 2
    const cy = anchor!.y + anchor!.height / 2
    expect(cx).toBeLessThan(400)
    expect(cy).toBeLessThan(500)
  })

  it('keeps every child when none is a >15x outlier (interior mode: no decorations, all room-sized)', () => {
    const wallGroup = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 })
    wallGroup.setAttribute('data-room', 'I01')
    wallGroup.append(fakeChild('path', { x: 0, y: 0, width: 80, height: 60 }))
    const floorGroup = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 })
    floorGroup.setAttribute('data-room', 'I01')
    floorGroup.append(
      fakeChild('path', { x: 2, y: 2, width: 76, height: 56 }),
      fakeChild('text', { x: 10, y: 10, width: 40, height: 12 }),
    )

    const anchor = markerAnchorBBox([wallGroup, floorGroup])

    // Nothing dropped -- union spans the full room (wall path defines the
    // widest extent), matching the original whole-room-bbox behavior
    // interior mode wants.
    expect(anchor).toEqual({ x: 0, y: 0, width: 80, height: 60 })
  })

  it('falls back to the group\'s own bbox when it has no children', () => {
    const leaf = fakeRoom('A01', { x: 5, y: 5, width: 30, height: 20 })
    expect(markerAnchorBBox([leaf])).toEqual({ x: 5, y: 5, width: 30, height: 20 })
  })

  it('returns null when every bbox is degenerate (zero width and height)', () => {
    const room = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 })
    room.append(fakeChild('g', { x: 10, y: 10, width: 0, height: 0 }))
    expect(markerAnchorBBox([room])).toBeNull()
  })
})

describe('focusRoom', () => {
  it('frames a fixed 175px-pad box around the room icon cluster (not the full label bbox), aspect-locked to 4:3', () => {
    const room = fakeRoom('A01', { x: 500, y: 400, width: 40, height: 40 })
    const svg = fakeSvg([room])

    focusRoom(svg, 'A01')

    // PAD=175 -> a 350x350 square before the aspect lock; 350/350=1 < 4/3,
    // so height stays the binding dimension and width grows to 350*4/3.
    // This is independent of the room's own bbox size (only its center
    // matters) -- exactly the point of framing on the icon cluster rather
    // than a label-length-dependent box.
    const vb = svg.viewBox.baseVal
    expect(vb.width).toBeCloseTo(350 * (4 / 3), 5)
    expect(vb.height).toBeCloseTo(350, 5)
    // Center of the room bbox is (520, 420).
    expect(vb.x + vb.width / 2).toBeCloseTo(520, 5)
    expect(vb.y + vb.height / 2).toBeCloseTo(420, 5)
  })

  it('never frames narrower than the 300px floor, regardless of room bbox size', () => {
    const tiny = fakeRoom('A01', { x: 10, y: 10, width: 1, height: 1 })
    const svg = fakeSvg([tiny])
    focusRoom(svg, 'A01')
    const vb = svg.viewBox.baseVal
    expect(vb.width).toBeGreaterThanOrEqual(300)
    expect(vb.width).toBeCloseTo(350 * (4 / 3), 5)
  })

  it('clamps the frame to stay inside the 1200x900 canvas for a room near the edge', () => {
    const room = fakeRoom('A01', { x: 0, y: 0, width: 10, height: 10 })
    const svg = fakeSvg([room])
    focusRoom(svg, 'A01')
    const vb = svg.viewBox.baseVal
    expect(vb.x).toBe(0)
    expect(vb.y).toBe(0)
    expect(vb.x + vb.width).toBeLessThanOrEqual(FULL_VB.w)
    expect(vb.y + vb.height).toBeLessThanOrEqual(FULL_VB.h)
  })

  it('invokes onChange with the same viewBox it applied to the svg', () => {
    const room = fakeRoom('A01', { x: 500, y: 400, width: 40, height: 40 })
    const svg = fakeSvg([room])
    const onChange = vi.fn()

    focusRoom(svg, 'A01', onChange)

    const vb = svg.viewBox.baseVal
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith({ x: vb.x, y: vb.y, w: vb.width, h: vb.height })
  })

  it('does nothing when the room id has no matching [data-room] group', () => {
    const svg = fakeSvg([fakeRoom('A01', { x: 0, y: 0, width: 10, height: 10 })])
    const before = svg.getAttribute('viewBox')
    const onChange = vi.fn()
    focusRoom(svg, 'nonexistent', onChange)
    expect(svg.getAttribute('viewBox')).toBe(before)
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('applyCurrentMarker', () => {
  it('centers the marker on the icon cluster, not the outlier-skewed whole-group union', () => {
    const room = fakeChild('g', { x: 0, y: 0, width: 0, height: 0 })
    room.setAttribute('data-room', 'A02')
    room.append(
      fakeChild('g', { x: 100, y: 100, width: 22, height: 19 }), // icon
      fakeChild('text', { x: 130, y: 95, width: 185, height: 22 }), // name label
      fakeChild('text', { x: 130, y: 118, width: 30, height: 14 }), // type tag
      fakeChild('g', { x: 400, y: 500, width: 293, height: 403 }), // decorations
    )
    const svg = fakeSvg([])
    svg.append(room)

    applyCurrentMarker(svg, 'A02')

    expect(room.classList.contains('neq-map-here')).toBe(true)
    const dot = svg.querySelector('.neq-map-here-dot')
    expect(dot).not.toBeNull()
    const cx = Number(dot!.getAttribute('cx'))
    const cy = Number(dot!.getAttribute('cy'))
    // Same expected center as the markerAnchorBBox unit test: x=100+215/2,
    // y=95+37/2 -- nowhere near the decoration group's 400..693/500..903
    // footprint, which is what the pre-fix whole-group union would have
    // centered on instead.
    expect(cx).toBeCloseTo(207.5, 5)
    expect(cy).toBeCloseTo(113.5, 5)
  })

  it('does not create a marker when currentLocationId has no matching [data-room]', () => {
    const svg = fakeSvg([])
    applyCurrentMarker(svg, 'nonexistent')
    expect(svg.querySelector('.neq-map-here-marker')).toBeNull()
  })
})
