// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { SceneImage } from './SceneImage'

afterEach(cleanup)
const scene = { image_url: '/scene-full.png', prompt: 'A quiet moonlit tower' }

it('opens a full scene preview, zooms only its image, and restores focus on close', () => {
  render(<SceneImage image={scene} />)
  const trigger = screen.getByRole('button', { name: /Open scene preview/ })
  trigger.focus()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('dialog', { name: 'Scene preview' })
  expect(dialog.parentElement).toBe(document.body)
  expect(document.body.style.overflow).toBe('hidden')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Zoom in' }))
  expect(within(dialog).getByLabelText('Zoom level').textContent).toBe('150%')
  expect(within(dialog).getByRole('img').style.transform).toContain('scale(1.5)')
  expect(trigger.querySelector('img')?.style.transform).toBe('')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Fit image' }))
  expect(within(dialog).getByLabelText('Zoom level').textContent).toBe('100%')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.body.style.overflow).toBe('')
  expect(document.activeElement).toBe(trigger)
})

it('supports two-finger zoom, clamps its range, and ends cancelled gestures', () => {
  render(<SceneImage image={scene} />)
  fireEvent.click(screen.getByRole('button', { name: /Open scene preview/ }))
  const dialog = screen.getByRole('dialog')
  const stage = within(dialog).getByLabelText('Zoomable scene')
  stage.getBoundingClientRect = () => ({ width: 400, height: 600, x: 0, y: 0, left: 0, top: 0, right: 400, bottom: 600, toJSON: () => ({}) })
  function pointer(type: string, id: number, x: number, y: number) {
    const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y })
    Object.defineProperties(event, { pointerId: { value: id }, pointerType: { value: 'touch' } })
    fireEvent(stage, event)
    return event
  }
  pointer('pointerdown', 1, 150, 300)
  pointer('pointerdown', 2, 250, 300)
  expect(pointer('pointermove', 2, 350, 300).defaultPrevented).toBe(true)
  expect(within(dialog).getByLabelText('Zoom level').textContent).toBe('200%')
  pointer('pointermove', 2, 5000, 300)
  expect(within(dialog).getByLabelText('Zoom level').textContent).toBe('500%')
  pointer('pointercancel', 1, 150, 300)
  pointer('pointercancel', 2, 5000, 300)
  pointer('pointermove', 2, 100, 300)
  expect(within(dialog).getByLabelText('Zoom level').textContent).toBe('500%')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Close scene preview' }))
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('reports an image load failure and allows retry instead of a broken thumbnail', () => {
  render(<SceneImage image={scene} />)
  fireEvent.error(screen.getByRole('img'))
  expect(screen.getByRole('status').textContent).toContain('unavailable')
  fireEvent.click(screen.getByRole('button', { name: 'Retry image' }))
  expect(screen.getByRole('button', { name: /Open scene preview/ })).toBeTruthy()
})
