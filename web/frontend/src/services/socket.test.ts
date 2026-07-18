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

describe('socket reconnect synchronization', () => {
  beforeEach(() => {
    socketMock.emit.mockClear()
  })

  it('allows Socket.IO to fall back to HTTP polling when WebSocket is unavailable', () => {
    expect(socketMock.io).toHaveBeenCalledWith()
  })

  it('re-requests all volatile world state after every connection', () => {
    const connect = socketMock.handlers.get('connect')
    expect(connect).toBeTypeOf('function')

    connect?.()
    connect?.()

    expect(socketMock.emit.mock.calls).toEqual([
      ['request_location_data'],
      ['request_party_data'],
      ['request_initiative_data'],
      ['request_location_data'],
      ['request_party_data'],
      ['request_initiative_data'],
    ])
  })
})
