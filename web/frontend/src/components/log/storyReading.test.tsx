// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useLog, useSession } from '../../stores'
import { GameLog } from './GameLog'
import { firstNewNarration, softenStoryArrival } from './storyReading'

vi.mock('../../services/socket', () => ({ emitC: vi.fn(), reconnect: vi.fn() }))
const initialLog = useLog.getState()
const initialSession = useSession.getState()
beforeEach(() => {
  useLog.setState(initialLog, true)
  useSession.setState(initialSession, true)
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('desktop reading position', () => {
  function setup() {
    useLog.getState().append({ type: 'narration', message_id: 'old', content: 'Earlier scene.' })
    render(<GameLog />)
    const log = screen.getByRole('log')
    Object.defineProperties(log, {
      clientHeight: { configurable: true, value: 400 },
      scrollHeight: { configurable: true, writable: true, value: 900 },
    })
    log.scrollTop = 500
    fireEvent.scroll(log)
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const top = this === log ? 100 : 100 + (Number(this.dataset.storyIndex) === 1 ? 900 : 1400) - log.scrollTop
      return { top, bottom: top + 1000, left: 0, right: 390, width: 390, height: 1000, x: 0, y: top, toJSON() {} }
    })
    Object.defineProperty(log, 'scrollHeight', { configurable: true, writable: true, value: 2400 })
    return log
  }

  it('opens a long response at its first lines and holds through later output, images and status', () => {
    const log = setup()
    act(() => useLog.getState().append({ type: 'narration', message_id: 'new', content: 'Opening paragraph.\n\n' + 'More story. '.repeat(100) }))
    expect(log.scrollTop).toBe(884)
    expect(screen.queryByRole('button', { name: /New from the DM/ })).toBeNull()
    act(() => {
      useSession.getState().setStatus({ message: 'Updating character info...', is_processing: true })
      useLog.getState().addImage({ image_url: '/scene.png', prompt: 'Opening paragraph.', source_message_id: 'new' })
    })
    expect(log.scrollTop).toBe(884)
    act(() => useLog.getState().append({ type: 'narration', message_id: 'continuation', content: 'Another paragraph follows.' }))
    expect(log.scrollTop).toBe(884)
  })

  it('leaves older reading untouched and opens the FIRST unread response on request', () => {
    const log = setup()
    log.scrollTop = 80
    fireEvent.scroll(log)
    act(() => useLog.getState().append({ type: 'narration', message_id: 'first', content: 'First unread response.' }))
    act(() => useLog.getState().append({ type: 'narration', message_id: 'second', content: 'Later unread response.' }))
    expect(log.scrollTop).toBe(80)
    fireEvent.click(screen.getByRole('button', { name: /New from the DM/ }))
    expect(log.scrollTop).toBe(884)
    expect(screen.queryByRole('button', { name: /New from the DM/ })).toBeNull()
  })

  it('keeps filling fully visible short replies, then holds when the next reply exceeds the screen', () => {
    const log = setup()
    let top = 500
    Object.defineProperty(log, 'scrollTop', { configurable: true, get: () => top,
      set: (value: number) => { top = Math.max(0, Math.min(value, log.scrollHeight - log.clientHeight)) } })
    Object.defineProperty(log, 'scrollHeight', { configurable: true, value: 1000 })
    act(() => useLog.getState().append({ type: 'narration', message_id: 'short', content: 'A brief answer.' }))
    expect(log.scrollTop).toBe(600)
    Object.defineProperty(log, 'scrollHeight', { configurable: true, value: 2400 })
    act(() => useLog.getState().append({ type: 'narration', message_id: 'long', content: 'A longer answer follows.' }))
    expect(log.scrollTop).toBe(1384)
    expect(screen.queryByRole('button', { name: /New from the DM/ })).toBeNull()
  })

  it('clears an unread action when its message is removed by campaign/history replacement', () => {
    const log = setup()
    log.scrollTop = 80
    fireEvent.scroll(log)
    act(() => useLog.getState().append({ type: 'narration', message_id: 'unread', content: 'Unread old campaign.' }))
    expect(screen.getByRole('button', { name: /New from the DM/ })).toBeTruthy()
    act(() => {
      useLog.getState().beginHistorySync()
      useLog.getState().replaceAll([{ type: 'narration', message_id: 'restored', content: 'Restored campaign.' }])
    })
    expect(screen.queryByRole('button', { name: /New from the DM/ })).toBeNull()
  })
})

it('detects fresh narration even when the ring length stays the same, without replaying cached history', () => {
  const previous = [{ type: 'narration' as const, message_id: 'old', content: 'Old' }]
  const current = [{ type: 'narration' as const, message_id: 'new', content: 'New' }]
  expect(firstNewNarration(current, previous, 0)).toBe(0)
  expect(firstNewNarration(current, previous, 1)).toBe(-1)
  expect(firstNewNarration([{ ...previous[0]! }], previous, 0)).toBe(-1)
})

it('honors reduced motion without delaying or hiding story text', () => {
  const node = document.createElement('div')
  node.textContent = 'The full story is readable.'
  const animate = vi.fn()
  node.animate = animate
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  softenStoryArrival(node)
  expect(animate).not.toHaveBeenCalled()
  expect(node.textContent).toBe('The full story is readable.')
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  softenStoryArrival(node)
  expect(animate).toHaveBeenCalledOnce()
})
