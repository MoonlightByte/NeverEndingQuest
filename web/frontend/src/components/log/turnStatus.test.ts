// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { useSession } from '../../stores'
import type { WaitRecord } from '../../contract/events'
import { useTurnStatus, waitStatusText } from './turnStatus'

function wait(overrides: Partial<WaitRecord> = {}): WaitRecord {
  return {
    kind: 'provider_call', purpose: 'turn', taskId: 'T001', provider: 'openai', providerName: 'OpenAI',
    attempt: 1, maxAttempts: null, elapsedMs: 5_000, phase: 'working', lastActivityMs: 2_000, retryInMs: null,
    ...overrides,
  }
}

describe('waitStatusText (#1271)', () => {
  it('names the purpose, the elapsed time and the transport phase', () => {
    expect(waitStatusText(wait(), 0)).toBe('The Dungeon Master is answering (5 s): OpenAI is working (last activity 2 s ago).')
    expect(waitStatusText(wait({ purpose: 'character_setup', phase: 'sent', elapsedMs: 42_000 }), 0))
      .toBe('Setting up your character (42 s): request sent, waiting for OpenAI to start.')
    expect(waitStatusText(wait({ purpose: 'starting_location', phase: 'connecting' }), 0))
      .toBe('Choosing your starting location (5 s): connecting to OpenAI.')
  })

  it('advances elapsed time and last activity from the local receipt clock', () => {
    expect(waitStatusText(wait(), 3_000)).toBe('The Dungeon Master is answering (8 s): OpenAI is working (last activity 5 s ago).')
  })

  it('adds the long-wait line at 60 s and formats minutes', () => {
    expect(waitStatusText(wait({ purpose: 'combat', elapsedMs: 205_000, phase: 'receiving' }), 0)).toBe(
      'Resolving the fight (3 min 25 s): answer arriving from OpenAI. '
      + "This can take a few minutes. Your turn is safe; there's no need to send it again.")
    expect(waitStatusText(wait({ elapsedMs: 59_000 }), 0)).not.toContain('Your turn is safe')
  })

  it('renders a retry wait from the typed attempt, with and without a bound', () => {
    expect(waitStatusText(wait({ purpose: 'character_setup', attempt: 2, maxAttempts: 5, retryInMs: 4_000, phase: null }), 0))
      .toBe('Setting up your character (5 s): attempt 1 of 5 failed; attempt 2 in 4 s.')
    expect(waitStatusText(wait({ attempt: 3, retryInMs: 1_500 }), 1_000))
      .toBe('The Dungeon Master is answering (6 s): attempt 2 failed; attempt 3 in 1 s.')
  })

  it('falls back for an unknown purpose or phase, and still shows elapsed time', () => {
    expect(waitStatusText(wait({ purpose: 'something_new', phase: 'odd' }), 0)).toBe('Waiting for OpenAI (5 s): waiting for OpenAI.')
    expect(waitStatusText(wait({ providerName: null, phase: null }), 0))
      .toBe('The Dungeon Master is answering (5 s): waiting for the AI provider.')
  })
})

describe('useTurnStatus', () => {
  let clock = 0
  beforeEach(() => {
    clock = 1_000
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'Date'] })
    vi.spyOn(performance, 'now').mockImplementation(() => clock)
    useSession.setState({ isProcessing: false, statusMessage: '', restoreRecoveryRequired: false, welcomeMessage: '', wait: null, waitReceivedAt: 0 })
  })
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

  it('ticks the elapsed time each second locally, with no network or store traffic', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    useSession.getState().setStatus({ message: 'Attempt 1, 5 s: ...', is_processing: true, wait: wait() })
    const before = useSession.getState()
    const { result } = renderHook(useTurnStatus)
    expect(result.current).toBe('The Dungeon Master is answering (5 s): OpenAI is working (last activity 2 s ago).')
    act(() => { clock += 3_000; vi.advanceTimersByTime(3_000) })
    expect(result.current).toBe('The Dungeon Master is answering (8 s): OpenAI is working (last activity 5 s ago).')
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(useSession.getState()).toBe(before)
  })

  it('ignores a wall-clock jump: only the monotonic clock moves elapsed time', () => {
    useSession.getState().setStatus({ message: '', is_processing: true, wait: wait() })
    const { result } = renderHook(useTurnStatus)
    act(() => { vi.setSystemTime(Date.now() + 3_600_000); clock += 1_000; vi.advanceTimersByTime(1_000) })
    expect(result.current).toBe('The Dungeon Master is answering (6 s): OpenAI is working (last activity 3 s ago).')
  })

  it('shows a busy status without a wait exactly as the server wrote it', () => {
    for (const message of ['Updating character info...', 'Processing combat round...', 'Compressing conversation history...']) {
      useSession.getState().setStatus({ message, is_processing: true })
      const { result, unmount } = renderHook(useTurnStatus)
      expect(result.current).toBe(message)
      unmount()
    }
    useSession.getState().setStatus({ message: '', is_processing: true })
    expect(renderHook(useTurnStatus).result.current).toBe('Working…')
  })

  it('shows a terminal failure line verbatim once the server sends it without a wait (C6, Sentinel N1)', () => {
    useSession.getState().setStatus({ message: 'Attempt 1, 5 s: ...', is_processing: true, wait: wait() })
    const { result } = renderHook(useTurnStatus)
    expect(result.current).toContain('The Dungeon Master is answering')
    const refusal = 'The provider refused the API key (401). Open Settings and save the provider configuration to retry.'
    act(() => { useSession.getState().setStatus({ message: refusal, is_processing: true }) })
    expect(useSession.getState().wait).toBeNull()
    expect(result.current).toBe(refusal)
  })

  it('drops the wait when the status stops processing, and keeps recovery and welcome lines', () => {
    useSession.getState().setStatus({ message: 'x', is_processing: true, wait: wait() })
    useSession.getState().setStatus({ message: 'Enter your command:', is_processing: false, wait: wait() })
    expect(useSession.getState().wait).toBeNull()
    useSession.setState({ welcomeMessage: 'The DM is recalling your journey...' })
    expect(renderHook(useTurnStatus).result.current).toBe('The DM is recalling your journey... You can act anytime.')
    useSession.setState({ restoreRecoveryRequired: true, statusMessage: 'Gameplay is paused. Choose Load, Reset, or Exit.' })
    expect(renderHook(useTurnStatus).result.current).toBe('Gameplay is paused. Choose Load, Reset, or Exit.')
  })
})

describe('no status text is read (#1271 C5)', () => {
  it('leaves no turnStatusText and no regex over a status message in src', () => {
    const root = join(__dirname, '../..')
    const files: string[] = []
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name)
        if (statSync(path).isDirectory()) walk(path)
        else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.test.ts')) files.push(path)
      }
    }
    walk(root)
    const hits = files.filter((file) => {
      const text = readFileSync(file, 'utf8')
      return /turnStatusText|\.test\((message|welcome|statusMessage|status\.message)\)/.test(text)
    })
    expect(hits).toEqual([])
  })
})
