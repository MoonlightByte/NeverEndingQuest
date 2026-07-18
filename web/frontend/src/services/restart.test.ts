// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { cancelPendingRestart, hasServerRestarted } from './restart'

describe('restart process identity', () => {
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
