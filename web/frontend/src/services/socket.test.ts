import { beforeEach, describe, expect, it, vi } from 'vitest'

const socketMock = vi.hoisted(() => ({
  handlers: new Map<string, (...args: unknown[]) => void>(),
  emit: vi.fn(),
  connected: false,
  on: vi.fn((event: string, handler: (...args: unknown[]) => void) => {
    socketMock.handlers.set(event, handler)
  }),
  io: vi.fn(),
}))

vi.mock('socket.io-client', () => ({
  io: (...args: unknown[]) => {
    socketMock.io(...args)
    return socketMock
  },
}))

import { emitC } from './socket'
import { useDialogs, useSession } from '../stores'

const initialSession = useSession.getState()

describe('socket reconnect synchronization', () => {
  beforeEach(() => {
    socketMock.emit.mockClear()
    socketMock.connected = false
    useSession.setState(initialSession, true)
    useDialogs.setState({ moduleOperation: null, actionResult: null })
  })

  it('allows Socket.IO to fall back to HTTP polling when WebSocket is unavailable', () => {
    expect(socketMock.io).toHaveBeenCalledWith()
  })

  it('re-requests all volatile world state after every connection', () => {
    const connect = socketMock.handlers.get('connect')
    expect(connect).toBeTypeOf('function')

    socketMock.connected = true
    connect?.()
    connect?.()

    expect(socketMock.emit.mock.calls.map(([event]) => event)).toEqual([
      'request_location_data', 'request_party_data', 'request_initiative_data', 'request_ui_snapshot',
      'request_player_data', 'request_player_data', 'request_player_data', 'request_player_data',
      'request_plot_data', 'request_storage_data', 'request_map_data',
      'request_location_data', 'request_party_data', 'request_initiative_data', 'request_ui_snapshot',
      'request_player_data', 'request_player_data', 'request_player_data', 'request_player_data',
      'request_plot_data', 'request_storage_data', 'request_map_data',
    ])
    for (const [event, payload] of socketMock.emit.mock.calls) {
      if (event === 'request_player_data') expect(payload).toMatchObject({ dataType: expect.any(String) })
      else expect(payload).toBeUndefined()
    }
  })

  it('adds request metadata only after the current connection advertises support', () => {
    socketMock.connected = true
    socketMock.handlers.get('connect')?.()
    socketMock.handlers.get('location_data_response')?.({ data: null, error: 'not ready' })
    socketMock.handlers.get('connected')?.({
      data: 'Connected',
      capabilities: { protocol_version: 1, request_metadata: true },
      server_instance_id: 'server-a',
    })

    socketMock.emit.mockClear()
    const requestId = emitC('request_location_data', undefined)
    expect(requestId).toMatch(/^e\d+-\d+$/)
    expect(socketMock.emit).toHaveBeenCalledWith('request_location_data', { request_id: requestId })
  })

  it('does not buffer periodic hydration requests while disconnected', () => {
    socketMock.connected = true
    socketMock.handlers.get('connect')?.()
    socketMock.emit.mockClear()
    socketMock.connected = false
    socketMock.handlers.get('disconnect')?.()

    emitC('request_location_data', undefined)
    emitC('request_player_data', { dataType: 'stats' })

    expect(socketMock.emit).not.toHaveBeenCalled()
  })

  it('does not resurrect an old terminal module modal on a fresh page snapshot', () => {
    socketMock.connected = true
    socketMock.handlers.get('connect')?.()
    socketMock.handlers.get('connected')?.({ data: 'Connected', capabilities: { request_metadata: true }, server_instance_id: 'server-a' })
    socketMock.handlers.get('ui_state_snapshot')?.({
      revision: 1,
      server_instance_id: 'server-a',
      game_running: true,
      is_processing: false,
      status_message: 'Ready',
      operations: {
        compression: null,
        update: null,
        module: { build_id: 'finished-build', stage: 9, total_stages: 9, stage_name: 'Ready', percentage: 100, message: 'Done', status: 'published', terminal: true, success: true },
      },
    })
    expect(useDialogs.getState().moduleOperation).toBeNull()
  })

  it('uses a terminal module snapshot to heal a build this client saw running', () => {
    socketMock.handlers.get('module_creation_progress')?.({ build_id: 'active-build', stage: 4, total_stages: 9, stage_name: 'Building', percentage: 40, message: 'Working', status: 'running', terminal: false })
    socketMock.connected = true
    socketMock.handlers.get('connect')?.()
    socketMock.handlers.get('connected')?.({ data: 'Connected', capabilities: { request_metadata: true }, server_instance_id: 'server-a' })
    socketMock.handlers.get('ui_state_snapshot')?.({
      revision: 2,
      server_instance_id: 'server-a',
      game_running: true,
      is_processing: false,
      status_message: 'Ready',
      operations: {
        compression: null,
        update: null,
        module: { build_id: 'active-build', stage: 9, total_stages: 9, stage_name: 'Ready', percentage: 100, message: 'Done', status: 'published', terminal: true, success: true },
      },
    })
    expect(useDialogs.getState().moduleOperation).toMatchObject({ buildId: 'active-build', terminal: true, success: true })
  })

  it('rejects stale operation state with the rest of an old snapshot revision', () => {
    socketMock.connected = true
    socketMock.handlers.get('connect')?.()
    socketMock.handlers.get('connected')?.({ data: 'Connected', capabilities: { request_metadata: true }, server_instance_id: 'server-a' })
    socketMock.handlers.get('ui_state_snapshot')?.({
      revision: 2,
      server_instance_id: 'server-a',
      game_running: true,
      is_processing: false,
      status_message: 'Ready',
      operations: {
        compression: null,
        update: { status: 'complete', log: ['Done'], error: null, complete: 'Update complete!' },
        module: null,
      },
    })
    const staleRequestId = emitC('request_ui_snapshot', undefined)
    socketMock.handlers.get('ui_state_snapshot')?.({
      request_id: staleRequestId,
      revision: 1,
      server_instance_id: 'server-a',
      game_running: true,
      is_processing: false,
      status_message: 'Updating',
      operations: {
        compression: null,
        update: { status: 'running', log: ['Still working'], error: null, complete: null },
        module: null,
      },
    })

    expect(useDialogs.getState().update).toEqual({
      running: false,
      log: ['Done'],
      error: null,
      complete: 'Update complete!',
    })
  })

  it('keeps the fixed legacy-safe exit copy when the server acknowledges exit', () => {
    useDialogs.getState().setActionResult({
      kind: 'exit',
      message: 'You can now safely close this browser tab.',
    })

    socketMock.handlers.get('exit_acknowledged')?.({ message: 'Exit acknowledged' })

    expect(useDialogs.getState().actionResult).toEqual({
      kind: 'exit',
      message: 'You can now safely close this browser tab.',
    })
  })
})
