// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { cancelPendingRestart, hasServerRestarted, prepareForServerRestart } from './restart'

describe('restart process identity', () => {
  it('does not overwrite a newer restart marker when canceled preparation resolves late', async () => {
    let resolveOld!: (response: Response) => void
    let current = true
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ server_instance_id: 'newer-server' })))
    try {
      const old = prepareForServerRestart(() => current)
      current = false
      await prepareForServerRestart()
      resolveOld(new Response(JSON.stringify({ server_instance_id: 'older-server' })))
      await old
      expect(sessionStorage.getItem('neq_restart_server_instance')).toBe('newer-server')
    } finally {
      fetchMock.mockRestore()
      sessionStorage.clear()
    }
  })
  it('does not mistake the still-running old process for the replacement', () => {
    expect(hasServerRestarted('server-a', 'server-a')).toBe(false)
  })

  it('recognizes a changed process even when no outage was observed', () => {
    expect(hasServerRestarted('server-a', 'server-b')).toBe(true)
  })

  it('uses an observed outage when no baseline could be captured', () => {
    expect(hasServerRestarted(null, 'server-b', true)).toBe(true)
    expect(hasServerRestarted(null, 'server-b', false)).toBe(false)
  })

  it('does not accept a healthy process for an unavailable baseline until a transition is observed', () => {
    expect(hasServerRestarted('unavailable', 'server-a', false)).toBe(false)
    expect(hasServerRestarted('unavailable', 'server-b', true)).toBe(true)
  })

  it('clears a pending marker when an update fails without restarting', () => {
    window.sessionStorage.setItem('neq_restart_server_instance', 'server-a')
    cancelPendingRestart()
    expect(window.sessionStorage.getItem('neq_restart_server_instance')).toBeNull()
  })
})
