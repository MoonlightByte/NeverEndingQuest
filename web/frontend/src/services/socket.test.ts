import { beforeEach, describe, expect, it, vi } from 'vitest'

const socketMock = vi.hoisted(() => ({
  handlers: new Map<string, (...args: unknown[]) => void>(),
  emit: vi.fn(),
  on: vi.fn((event: string, handler: (...args: unknown[]) => void) => {
    socketMock.handlers.set(event, handler)
  }),
  io: vi.fn(),
}))

vi.mock('socket.io-client', () => ({
  io: (...args: unknown[]) => {
    socketMock.io(...args)
    return { on: socketMock.on, emit: socketMock.emit }
  },
}))

import './socket'
import { useDialogs } from '../stores'

describe('socket reconnect synchronization', () => {
  beforeEach(() => {
    socketMock.emit.mockClear()
    useDialogs.setState({ moduleOperation: null })
  })

  it('allows Socket.IO to fall back to HTTP polling when WebSocket is unavailable', () => {
    expect(socketMock.io).toHaveBeenCalledWith()
  })

  it('re-requests all volatile world state after every connection', () => {
    const connect = socketMock.handlers.get('connect')
    expect(connect).toBeTypeOf('function')

    connect?.()
    connect?.()

    expect(socketMock.emit.mock.calls.map(([event]) => event)).toEqual([
      'request_location_data', 'request_party_data', 'request_initiative_data', 'request_ui_snapshot',
      'request_player_data', 'request_player_data', 'request_player_data', 'request_player_data',
      'request_plot_data', 'request_storage_data',
      'request_location_data', 'request_party_data', 'request_initiative_data', 'request_ui_snapshot',
      'request_player_data', 'request_player_data', 'request_player_data', 'request_player_data',
      'request_plot_data', 'request_storage_data',
    ])
    for (const [, payload] of socketMock.emit.mock.calls) {
      expect(payload).toMatchObject({ request_id: expect.stringMatching(/^e\d+-\d+$/) })
    }
  })

  it('does not resurrect an old terminal module modal on a fresh page snapshot', () => {
    socketMock.handlers.get('connect')?.()
    const request = socketMock.emit.mock.calls.find(([event]) => event === 'request_ui_snapshot')?.[1] as { request_id: string }
    socketMock.handlers.get('ui_state_snapshot')?.({
      request_id: request.request_id,
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
    socketMock.handlers.get('connect')?.()
    const request = socketMock.emit.mock.calls.find(([event]) => event === 'request_ui_snapshot')?.[1] as { request_id: string }
    socketMock.handlers.get('ui_state_snapshot')?.({
      request_id: request.request_id,
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
})
