// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useSpellReference } from './useSpellReference'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })

it('shares one bounded request, exposes timeout and retries the reference without losing subscribers', async () => {
  vi.useFakeTimers()
  const request = vi.fn((_url: string, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
  }))
  vi.stubGlobal('fetch', request)
  const first = renderHook(useSpellReference)
  const second = renderHook(useSpellReference)
  expect(request).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
  expect(first.result.current.status).toBe('error')
  expect(second.result.current.status).toBe('error')
  const data = { goodberry: { name: 'Goodberry', level: 1 } }
  request.mockImplementationOnce(async () => ({ ok: true, json: async () => data }))
  await act(async () => { second.result.current.retry(); await vi.advanceTimersByTimeAsync(0) })
  expect(request).toHaveBeenCalledTimes(2)
  expect(first.result.current.status).toBe('ready')
  expect(second.result.current.data).toEqual(data)
})
