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
  readAnchor,
  structuralKey,
  wirePanZoom,
  zoomPercent,
} from './useMapPanZoom'

/** A `[data-room]` group carrying `data-anchor="x,y"`, as the vendored renderer stamps it. */
function fakeRoom(id: string, anchor: { x: number; y: number }): SVGGraphicsElement {
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'g') as unknown as SVGGraphicsElement
  el.setAttribute('data-room', id)
  el.setAttribute('data-anchor', `${anchor.x},${anchor.y}`)
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

  // The two fit tests below are the aspect-lock pair: with PAD=280 on every
  // side, whichever dimension is proportionally smaller gets grown to reach
  // 4:3. All the expected numbers are derived in the comments.

  it('locks 4:3 by growing the width when height is the binding dimension', () => {
    const svg = fakeSvg([
      fakeRoom('A01', { x: 500, y: 400 }),
      fakeRoom('A02', { x: 640, y: 460 }),
      // Present in the SVG but NOT in revealedIds -- must not affect the fit.
      fakeRoom('A99', { x: 0, y: 0 }),
    ])
    const vb = computeAutoFitViewBox(svg, ['A01', 'A02'])

    // Anchor union is x 500..640 (140 wide), y 400..460 (60 tall); padded by
    // 280 on every side that is x 220..920, y 120..740 -> 700x620.
    // 700/620 = 1.129 < 4/3, so height binds and the width grows to
    // 620 * 4/3 = 826.67 (inside [400, 1200], so neither clamp fires).
    // Centre (570, 430) -> x = 570 - 826.67/2 = 156.67, y = 430 - 310 = 120,
    // both inside the 1200x900 canvas so the edge clamp does not move them.
    expect(vb.h).toBeCloseTo(620, 5)
    expect(vb.w).toBeCloseTo(620 * (4 / 3), 5)
    expect(vb.x).toBeCloseTo(156.666666, 4)
    expect(vb.y).toBeCloseTo(120, 5)
    expect(vb.w / vb.h).toBeCloseTo(4 / 3, 5)
  })

  it('locks 4:3 by growing the height when width is the binding dimension', () => {
    const svg = fakeSvg([
      fakeRoom('A', { x: 300, y: 400 }),
      fakeRoom('B', { x: 700, y: 400 }),
      fakeRoom('C', { x: 1100, y: 800 }),
    ])
    const vb = computeAutoFitViewBox(svg, ['A', 'B'])

    // Anchor union is x 300..700 (400 wide), y 400..400 (a flat line); padded
    // by 280 that is x 20..980, y 120..680 -> 960x560. 960/560 = 1.71 > 4/3,
    // so width binds and the height grows to 960 * 3/4 = 720.
    // Centre (500, 400) -> x = 500 - 480 = 20, y = 400 - 360 = 40; both inside
    // the canvas (x <= 1200-960 = 240, y <= 900-720 = 180), so no edge clamp.
    expect(vb.w).toBeCloseTo(960, 5)
    expect(vb.h).toBeCloseTo(720, 5)
    expect(vb.x).toBeCloseTo(20, 5)
    expect(vb.y).toBeCloseTo(40, 5)
    expect(vb.w / vb.h).toBeCloseTo(4 / 3, 5)
  })

  it('never produces a width below the 400px floor for a single anchor', () => {
    // The fixed 280px padding on every side already guarantees a width well
    // above MIN_W=400 for any single anchor point: it pads out to a 560x560
    // square (280 each side, zero-size union), which is aspect-locked to
    // 560*4/3 = 746.67 wide. This exercises the floor as a property rather
    // than expecting the clamp branch itself to fire -- with PAD=280 it
    // can't, for any single room, however placed.
    const svg = fakeSvg([fakeRoom('A01', { x: 0, y: 0 })])
    const vb = computeAutoFitViewBox(svg, ['A01'])
    expect(vb.w).toBeGreaterThanOrEqual(400)
    expect(vb.w).toBeCloseTo(560 * (4 / 3), 5)
    expect(vb.h).toBeCloseTo(560, 5)
  })

  it('clamps a huge span down to the 1200px maximum width', () => {
    const svg = fakeSvg([fakeRoom('A01', { x: 0, y: 0 }), fakeRoom('A02', { x: 5000, y: 4000 })])
    const vb = computeAutoFitViewBox(svg, ['A01', 'A02'])
    expect(vb.w).toBe(1200)
    expect(vb.h).toBeCloseTo(900, 5)
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

describe('readAnchor', () => {
  const group = (anchor?: string) => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
    if (anchor) g.setAttribute('data-anchor', anchor)
    return g
  }
  it('parses data-anchor="x,y" from the first group carrying it', () => {
    expect(readAnchor([group(), group('648.5,308')])).toEqual({ x: 648.5, y: 308 })
  })
  it('returns null when no group carries an anchor or it is malformed', () => {
    expect(readAnchor([group(), group('nope')])).toBeNull()
    expect(readAnchor([])).toBeNull()
  })
})

describe('focusRoom', () => {
  it('frames a fixed 175px-pad box around the room anchor, aspect-locked to 4:3', () => {
    const room = fakeRoom('A01', { x: 520, y: 420 })
    const svg = fakeSvg([room])

    focusRoom(svg, 'A01')

    // PAD=175 -> a 350x350 square before the aspect lock; 350/350=1 < 4/3,
    // so height stays the binding dimension and width grows to 350*4/3.
    const vb = svg.viewBox.baseVal
    expect(vb.width).toBeCloseTo(350 * (4 / 3), 5)
    expect(vb.height).toBeCloseTo(350, 5)
    // Center is the room's anchor, (520, 420).
    expect(vb.x + vb.width / 2).toBeCloseTo(520, 5)
    expect(vb.y + vb.height / 2).toBeCloseTo(420, 5)
  })

  it('never frames narrower than the 300px floor, regardless of the anchor position', () => {
    const tiny = fakeRoom('A01', { x: 10, y: 10 })
    const svg = fakeSvg([tiny])
    focusRoom(svg, 'A01')
    const vb = svg.viewBox.baseVal
    expect(vb.width).toBeGreaterThanOrEqual(300)
    expect(vb.width).toBeCloseTo(350 * (4 / 3), 5)
  })

  it('clamps the frame to stay inside the 1200x900 canvas for a room near the edge', () => {
    const room = fakeRoom('A01', { x: 0, y: 0 })
    const svg = fakeSvg([room])
    focusRoom(svg, 'A01')
    const vb = svg.viewBox.baseVal
    expect(vb.x).toBe(0)
    expect(vb.y).toBe(0)
    expect(vb.x + vb.width).toBeLessThanOrEqual(FULL_VB.w)
    expect(vb.y + vb.height).toBeLessThanOrEqual(FULL_VB.h)
  })

  it('invokes onChange with the same viewBox it applied to the svg', () => {
    const room = fakeRoom('A01', { x: 520, y: 420 })
    const svg = fakeSvg([room])
    const onChange = vi.fn()

    focusRoom(svg, 'A01', onChange)

    const vb = svg.viewBox.baseVal
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith({ x: vb.x, y: vb.y, w: vb.width, h: vb.height })
  })

  it('does nothing when the room id has no matching [data-room] group', () => {
    const svg = fakeSvg([fakeRoom('A01', { x: 0, y: 0 })])
    const before = svg.getAttribute('viewBox')
    const onChange = vi.fn()
    focusRoom(svg, 'nonexistent', onChange)
    expect(svg.getAttribute('viewBox')).toBe(before)
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('applyCurrentMarker', () => {
  it('centers the marker on the room anchor', () => {
    const room = fakeRoom('A02', { x: 207.5, y: 113.5 })
    const svg = fakeSvg([room])

    applyCurrentMarker(svg, 'A02')

    expect(room.classList.contains('neq-map-here')).toBe(true)
    const dot = svg.querySelector('.neq-map-here-dot')
    expect(dot).not.toBeNull()
    const cx = Number(dot!.getAttribute('cx'))
    const cy = Number(dot!.getAttribute('cy'))
    expect(cx).toBeCloseTo(207.5, 5)
    expect(cy).toBeCloseTo(113.5, 5)
  })

  it('does not create a marker when currentLocationId has no matching [data-room]', () => {
    const svg = fakeSvg([])
    applyCurrentMarker(svg, 'nonexistent')
    expect(svg.querySelector('.neq-map-here-marker')).toBeNull()
  })
})

describe('wirePanZoom drag threshold', () => {
  it('ignores a 3px jiggle but pans on a 5px drag', () => {
    const stage = document.createElement('div')
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement
    svg.setAttribute('viewBox', '0 0 1200 900')
    Object.defineProperty(svg, 'clientWidth', { value: 600 })
    stage.append(svg)
    document.body.append(stage)
    stage.setPointerCapture = () => {}
    stage.releasePointerCapture = () => {}
    stage.hasPointerCapture = () => false
    const onChange = vi.fn()
    const off = wirePanZoom(stage, () => svg, onChange)
    const ev = (type: string, x: number) =>
      stage.dispatchEvent(new PointerEvent(type, { clientX: x, clientY: 100, pointerId: 1, bubbles: true }))
    ev('pointerdown', 100)
    ev('pointermove', 103)
    ev('pointerup', 103)
    expect(onChange).not.toHaveBeenCalled()
    ev('pointerdown', 100)
    ev('pointermove', 105)
    expect(onChange).toHaveBeenCalledTimes(1)
    off()
  })
})
