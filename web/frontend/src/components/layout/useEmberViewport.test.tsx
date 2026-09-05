// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useEmberViewport } from './useEmberViewport'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('subscribes to the desktop boundary and cleans up its listener', () => {
  let change: (() => void) | undefined
  const media = {
    matches: true,
    addEventListener: vi.fn((_event: string, callback: () => void) => { change = callback }),
    removeEventListener: vi.fn(),
  }
  const matchMedia = vi.fn(() => media)
  vi.stubGlobal('matchMedia', matchMedia)
  const { result, unmount } = renderHook(useEmberViewport)
  expect(result.current).toBe(true)
  expect(matchMedia).toHaveBeenCalledWith('(min-width: 1024px)')
  act(() => { media.matches = false; change?.() })
  expect(result.current).toBe(false)
  unmount()
  expect(media.removeEventListener).toHaveBeenCalledWith('change', change)
})

it('retains the original presentation if media queries are unavailable', () => {
  vi.stubGlobal('matchMedia', undefined)
  const { result } = renderHook(useEmberViewport)
  expect(result.current).toBe(false)
})
