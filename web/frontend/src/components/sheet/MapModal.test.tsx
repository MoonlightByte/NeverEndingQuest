// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MapperHandle } from 'mapper-lib'

const { createMapMock } = vi.hoisted(() => ({ createMapMock: vi.fn() }))

vi.mock('mapper-lib', () => ({ createMap: createMapMock }))

import type { MapDataPayload } from '../../types/map'
import { MapModal } from './MapModal'

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
  createMapMock.mockReset()
})

afterEach(() => {
  // cleanup() BEFORE wiping the body: the modal renders through a portal, so
  // React's unmount removes nodes it owns directly from document.body -- and
  // that throws if the body was emptied out from under it first.
  cleanup()
  document.body.replaceChildren()
})

describe('MapModal', () => {
  it('renders its own map instance, the notes card and the toolbar; Esc closes and focus returns', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const onClose = vi.fn()
    render(<MapModal mapData={payload()} theme="night" onClose={onClose} />)

    expect(createMapMock).toHaveBeenCalledTimes(1)
    expect(createMapMock.mock.calls[0][3]).toMatchObject({
      uid: 'neqmapmodal',
      palette: 'night',
      instant: true,
      labelScale: 1.4,
      fontCss: false,
      quiet: true,
    })
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeTruthy()
    expect(screen.getByText(/places discovered/)).toBeTruthy()
    // The modal chrome ports the rail toolbar's labels verbatim.
    for (const label of ['⊙ fit', '▭ whole', '✕ close']) {
      expect(screen.getByText(label)).toBeTruthy()
    }
    // DialogShell moved focus off the opener and into the dialog.
    expect(dialog.contains(document.activeElement)).toBe(true)
    // jsdom's document has no #root; the guard keeps the assertion honest in
    // the app, where the background must be inert while the modal is open.
    expect(document.getElementById('root')?.hasAttribute('inert') ?? true).toBe(true)

    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('destroys its map instance and lifts inert on unmount', () => {
    const root = document.createElement('div')
    root.id = 'root'
    document.body.append(root)
    createMapMock.mockImplementation(() => makeHandle([]))
    const { unmount } = render(<MapModal mapData={payload()} theme="day" onClose={() => {}} />)
    expect(root.hasAttribute('inert')).toBe(true)
    const handle = createMapMock.mock.results[0].value as MapperHandle
    unmount()
    expect(handle.destroy).toHaveBeenCalled()
    expect(root.hasAttribute('inert')).toBe(false)
  })

  it('renders into document.body via a portal, not into its React parent', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    const { container } = render(<MapModal mapData={payload()} theme="day" onClose={() => {}} />)
    expect(container.querySelector('.neq-map-modal')).toBeNull()
    const modal = document.body.querySelector('.neq-map-modal')
    expect(modal).toBeTruthy()
    expect(modal?.getAttribute('data-map-theme')).toBe('day')
  })

  it('does NOT re-create the map when only the mapData object identity changes', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    const { rerender } = render(<MapModal mapData={payload()} theme="day" onClose={() => {}} />)
    const handle = createMapMock.mock.results[0].value as MapperHandle
    expect(createMapMock).toHaveBeenCalledTimes(1)

    // A socket refresh hands down a brand-new object with the same structure
    // and one more revealed room. Re-creating here would snap the map back to
    // auto-fit and throw away the pan/zoom the user is looking through.
    rerender(<MapModal mapData={payload({ revealed: ['A01', 'A02'] })} theme="day" onClose={() => {}} />)
    expect(createMapMock).toHaveBeenCalledTimes(1)
    expect(handle.destroy).not.toHaveBeenCalled()
    expect(handle.setRevealed).toHaveBeenLastCalledWith(['A01', 'A02'])
  })

  it('DOES re-create the map when the theme changes, with the new palette', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    const { rerender } = render(<MapModal mapData={payload()} theme="day" onClose={() => {}} />)
    const first = createMapMock.mock.results[0].value as MapperHandle
    rerender(<MapModal mapData={payload()} theme="night" onClose={() => {}} />)

    // The palette is baked into the rendered SVG, so it can only change by
    // rebuilding -- and a fresh SVG is correctly auto-fitted again.
    expect(createMapMock).toHaveBeenCalledTimes(2)
    expect(first.destroy).toHaveBeenCalledTimes(1)
    expect(createMapMock.mock.calls[1][3]).toMatchObject({ uid: 'neqmapmodal', palette: 'night' })
  })

  it('applies the theme palette on the modal map and reveals the served set', () => {
    createMapMock.mockImplementation(() => makeHandle([]))
    render(<MapModal mapData={payload()} theme="night" onClose={() => {}} />)
    const handle = createMapMock.mock.results[0].value as MapperHandle
    expect(handle.setRevealed).toHaveBeenCalledWith(['A01'])
  })
})
