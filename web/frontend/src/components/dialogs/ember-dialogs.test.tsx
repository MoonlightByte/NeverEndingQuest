// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DialogShell } from './DialogShell'
import { SettingsMenu } from '../settings/SettingsMenu'
import { createPortal } from 'react-dom'
import { useRef } from 'react'
import { useModalLayer } from './useModalLayer'
vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('arbitrates nested Escape and restores scroll locking only after the last dialog', () => {
  const parentClose = vi.fn()
  const childClose = vi.fn()
  const { rerender } = render(<><DialogShell title="Parent" onClose={parentClose}><button>Parent action</button></DialogShell><DialogShell title="Child" onClose={childClose}><button>Child action</button></DialogShell></>)
  expect(document.body.style.overflow).toBe('hidden')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(childClose).toHaveBeenCalledOnce()
  expect(parentClose).not.toHaveBeenCalled()
  rerender(<DialogShell title="Parent" onClose={parentClose}><button>Parent action</button></DialogShell>)
  expect(document.body.style.overflow).toBe('hidden')
  cleanup()
  expect(document.body.style.overflow).toBe('')
})

it('keeps all public settings in desktop sections and closes from Done', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  render(<SettingsMenu />)
  fireEvent.click(screen.getByRole('button', { name: 'Settings' }))
  expect(screen.getByRole('dialog', { name: 'Settings' })).toBeTruthy()
  expect(screen.getByRole('combobox', { name: 'Provider' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Voice & images' }))
  expect(screen.getByRole('checkbox', { name: 'AI Images' })).toBeTruthy()
  expect(screen.queryByRole('combobox', { name: 'Provider' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Map' }))
  expect(screen.getByRole('combobox', { name: 'Map style' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Done' }))
  expect(screen.queryByRole('dialog')).toBeNull()
})

function InspectionLayer() {
  const ref = useRef<HTMLDivElement>(null)
  useModalLayer(ref, undefined, { modal: false })
  return createPortal(<div ref={ref} data-testid="inspection"><button>Inspect action</button></div>, document.body)
}
it('reconciles a new in-root modal above an older body portal and permits inspection', () => {
  const portal = createPortal(<DialogShell title="Older portal" onClose={vi.fn()}><button>Older action</button></DialogShell>, document.body)
  const { container, rerender } = render(<>{portal}</>)
  expect(container.inert).toBe(true)
  rerender(<>{portal}<DialogShell title="New root modal" onClose={vi.fn()}><button>New action</button></DialogShell></>)
  expect(container.inert).toBe(false)
  const oldOverlay = screen.getByRole('heading', { name: 'Older portal', hidden: true }).closest('.ember-dialog-overlay') as HTMLElement
  const newOverlay = screen.getByRole('heading', { name: 'New root modal' }).closest('.ember-dialog-overlay') as HTMLElement
  expect(oldOverlay.inert).toBe(true)
  expect(Number(newOverlay.style.zIndex)).toBeGreaterThan(Number(oldOverlay.style.zIndex))
  rerender(<>{portal}<DialogShell title="New root modal" onClose={vi.fn()}><button>New action</button></DialogShell><InspectionLayer /></>)
  expect(screen.getByTestId('inspection').inert).not.toBe(true)
  expect(container.inert).toBe(false)
})
