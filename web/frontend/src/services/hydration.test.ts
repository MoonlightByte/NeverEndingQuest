import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CLIENT_EVENT_ARITY } from '../contract/events'
import { HydrationCoordinator } from './hydration'

describe('client event arity contract', () => {
  it('is exhaustive and preserves the legacy zero-argument hydration packets', () => {
    expect(Object.keys(CLIENT_EVENT_ARITY)).toHaveLength(32)
    expect(CLIENT_EVENT_ARITY.request_location_data).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_party_data).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_initiative_data).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_plot_data).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_storage_data).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_ui_snapshot).toBe(0)
    expect(CLIENT_EVENT_ARITY.request_player_data).toBe(1)
  })
})

describe('HydrationCoordinator', () => {
  const wire = vi.fn()
  let coordinator: HydrationCoordinator

  beforeEach(() => {
    vi.useFakeTimers()
    wire.mockReset()
    coordinator = new HydrationCoordinator(wire, { retryMs: 100, maxAttempts: 2 })
    coordinator.beginConnection()
  })

  afterEach(() => {
    coordinator.dispose()
    vi.useRealTimers()
  })

  it('uses exact old-server arity until a capability is advertised', () => {
    expect(coordinator.request('request_party_data', undefined)).toBeUndefined()
    expect(wire).toHaveBeenCalledWith('request_party_data', undefined, 0)

    coordinator.accept('request_party_data', { members: [] })
    coordinator.advertise({ protocol_version: 1, request_metadata: true }, 'server-a')
    const requestId = coordinator.request('request_party_data', undefined)

    expect(requestId).toMatch(/^e1-\d+$/)
    expect(wire).toHaveBeenLastCalledWith(
      'request_party_data',
      { request_id: requestId },
      1,
    )
  })

  it('keeps historically one-argument requests at arity one without adding metadata', () => {
    coordinator.request('request_player_data', { dataType: 'stats' })
    expect(wire).toHaveBeenCalledWith(
      'request_player_data',
      { dataType: 'stats' },
      1,
    )
  })

  it('resets advertised capability and server identity for every connection', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    coordinator.beginConnection()
    coordinator.request('request_location_data', undefined)

    expect(coordinator.supportsRequestMetadata()).toBe(false)
    expect(coordinator.activeServerInstance()).toBeNull()
    expect(wire).toHaveBeenLastCalledWith('request_location_data', undefined, 0)
  })

  it('coalesces concurrent callers and retries a lost request once', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    const first = coordinator.request('request_location_data', undefined)
    const second = coordinator.request('request_location_data', undefined)
    expect(second).toBe(first)
    expect(wire).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(100)
    expect(wire).toHaveBeenCalledTimes(2)
    expect(wire.mock.calls[1]).toEqual(wire.mock.calls[0])

    vi.advanceTimersByTime(100)
    expect(coordinator.hasPending('request_location_data', undefined)).toBe(false)
  })

  it('turns a burst during an in-flight request into exactly one trailing refresh', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    const firstRequestId = coordinator.request('request_location_data', undefined)
    for (let index = 0; index < 20; index += 1) {
      expect(coordinator.request('request_location_data', undefined)).toBe(firstRequestId)
    }
    expect(wire).toHaveBeenCalledTimes(1)

    expect(coordinator.accept('request_location_data', {
      data: {},
      request_id: firstRequestId,
      server_instance_id: 'server-a',
    })).toBe(true)

    expect(wire).toHaveBeenCalledTimes(2)
    const trailingPayload = wire.mock.calls[1]?.[1] as { request_id?: string }
    expect(trailingPayload.request_id).toMatch(/^e1-\d+$/)
    expect(trailingPayload.request_id).not.toBe(firstRequestId)
    expect(coordinator.hasPending('request_location_data', undefined)).toBe(true)

    expect(coordinator.accept('request_location_data', {
      data: {},
      request_id: trailingPayload.request_id,
      server_instance_id: 'server-a',
    })).toBe(true)
    expect(wire).toHaveBeenCalledTimes(2)
    expect(coordinator.hasPending('request_location_data', undefined)).toBe(false)
  })

  it('tracks trailing refreshes independently for each player-data slice', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    const statsRequestId = coordinator.request('request_player_data', { dataType: 'stats' })
    const inventoryRequestId = coordinator.request('request_player_data', { dataType: 'inventory' })
    coordinator.request('request_player_data', { dataType: 'stats' })
    expect(wire).toHaveBeenCalledTimes(2)

    expect(coordinator.accept('request_player_data', {
      dataType: 'stats',
      request_id: statsRequestId,
      server_instance_id: 'server-a',
    })).toBe(true)
    expect(wire).toHaveBeenCalledTimes(3)

    expect(coordinator.accept('request_player_data', {
      dataType: 'inventory',
      request_id: inventoryRequestId,
      server_instance_id: 'server-a',
    })).toBe(true)
    expect(wire).toHaveBeenCalledTimes(3)
  })

  it('keeps player-data slices as independent single flights', () => {
    coordinator.request('request_player_data', { dataType: 'stats' })
    coordinator.request('request_player_data', { dataType: 'inventory' })
    coordinator.request('request_player_data', { dataType: 'stats' })
    expect(wire).toHaveBeenCalledTimes(2)
  })

  it('rejects a response from a different server instance', () => {
    coordinator.advertise({ request_metadata: true }, 'server-new')
    const requestId = coordinator.request('request_party_data', undefined)
    expect(coordinator.accept('request_party_data', {
      members: [],
      request_id: requestId,
      server_instance_id: 'server-old',
    })).toBe(false)
    expect(coordinator.hasPending('request_party_data', undefined)).toBe(true)
  })

  it('rejects an earlier connection request id after reconnect', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    const oldRequestId = coordinator.request('request_location_data', undefined)

    coordinator.beginConnection()
    coordinator.advertise({ request_metadata: true }, 'server-b')
    coordinator.request('request_location_data', undefined)

    expect(coordinator.accept('request_location_data', {
      data: {},
      request_id: oldRequestId,
      server_instance_id: 'server-a',
    })).toBe(false)
  })

  it('clears a matching request and lets the next caller refresh again', () => {
    coordinator.advertise({ request_metadata: true }, 'server-a')
    const requestId = coordinator.request('request_plot_data', undefined)
    expect(coordinator.accept('request_plot_data', {
      data: null,
      request_id: requestId,
      server_instance_id: 'server-a',
    })).toBe(true)
    expect(coordinator.hasPending('request_plot_data', undefined)).toBe(false)

    coordinator.request('request_plot_data', undefined)
    expect(wire).toHaveBeenCalledTimes(2)
  })
})
