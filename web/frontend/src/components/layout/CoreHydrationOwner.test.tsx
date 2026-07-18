// @vitest-environment jsdom
import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { emitC } from '../../services/socket'
import { useLog } from '../../stores'
import { CoreHydrationOwner } from './CoreHydrationOwner'

vi.mock('../../services/socket', () => ({ emitC: vi.fn() }))

const initialLog = useLog.getState()

describe('CoreHydrationOwner', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    useLog.setState(initialLog, true)
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('owns mount, log, and timer refreshes for all three core resources', () => {
    render(<CoreHydrationOwner />)
    expect(vi.mocked(emitC).mock.calls.map(([event]) => event)).toEqual([
      'request_location_data',
      'request_party_data',
      'request_initiative_data',
    ])

    act(() => useLog.getState().append({ type: 'narration', content: 'The gate opens.' }))
    expect(vi.mocked(emitC)).toHaveBeenCalledTimes(6)

    act(() => vi.advanceTimersByTime(5000))
    expect(vi.mocked(emitC)).toHaveBeenCalledTimes(9)
  })

  it('cleans up its subscription and interval', () => {
    const view = render(<CoreHydrationOwner />)
    view.unmount()
    vi.clearAllMocks()

    act(() => {
      useLog.getState().append({ type: 'narration', content: 'No owner remains.' })
      vi.advanceTimersByTime(5000)
    })
    expect(emitC).not.toHaveBeenCalled()
  })
})
