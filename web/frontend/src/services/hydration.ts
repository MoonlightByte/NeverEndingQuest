import type { ClientEvents, ResponseMeta, UiProtocolCapabilities } from '../contract/events'
import { CLIENT_EVENT_ARITY } from '../contract/events'

export const HYDRATION_EVENTS = [
  'request_location_data',
  'request_party_data',
  'request_initiative_data',
  'request_ui_snapshot',
  'request_player_data',
  'request_plot_data',
  'request_storage_data',
] as const

export type HydrationEvent = (typeof HYDRATION_EVENTS)[number]
export type HydrationPayload = ClientEvents[HydrationEvent]

type WireEmit = (event: HydrationEvent, payload: unknown, arity: 0 | 1) => void
type TimerHandle = ReturnType<typeof setTimeout>

interface PendingRequest {
  event: HydrationEvent
  payload: HydrationPayload
  requestId?: string
  epoch: number
  attempts: number
  dirty: boolean
  timer?: TimerHandle
}

export interface HydrationCoordinatorOptions {
  retryMs?: number
  maxAttempts?: number
}

export function isHydrationEvent(event: string): event is HydrationEvent {
  return (HYDRATION_EVENTS as readonly string[]).includes(event)
}

/** A request resource is more specific than an event for player-data slices. */
export function hydrationKey(event: HydrationEvent, payload: unknown): string {
  if (event === 'request_player_data' && payload && typeof payload === 'object') {
    return `${event}:${String((payload as Record<string, unknown>).dataType ?? '')}`
  }
  return event
}

export function responseHydrationKey(event: HydrationEvent, payload: unknown): string {
  return hydrationKey(event, payload)
}

/**
 * Owns compatibility negotiation, correlation, coalescing, and bounded retry
 * for read-only UI hydration requests.  It deliberately has no store imports,
 * which makes the transport state machine deterministic to unit test.
 */
export class HydrationCoordinator {
  private readonly wireEmit: WireEmit
  private readonly pending = new Map<string, PendingRequest>()
  private readonly retryMs: number
  private readonly maxAttempts: number
  private epoch = 0
  private sequence = 0
  private metadataSupported = false
  private serverInstanceId: string | null = null

  constructor(wireEmit: WireEmit, options: HydrationCoordinatorOptions = {}) {
    this.wireEmit = wireEmit
    this.retryMs = options.retryMs ?? 2_000
    this.maxAttempts = Math.max(1, options.maxAttempts ?? 2)
  }

  beginConnection(): number {
    for (const request of this.pending.values()) {
      if (request.timer) clearTimeout(request.timer)
    }
    this.pending.clear()
    this.epoch += 1
    this.metadataSupported = false
    this.serverInstanceId = null
    return this.epoch
  }

  advertise(capabilities: UiProtocolCapabilities | undefined, serverInstanceId?: string): void {
    this.metadataSupported = capabilities?.request_metadata === true
    this.serverInstanceId = serverInstanceId || null
  }

  currentEpoch(): number {
    return this.epoch
  }

  activeServerInstance(): string | null {
    return this.serverInstanceId
  }

  supportsRequestMetadata(): boolean {
    return this.metadataSupported
  }

  /**
   * Start a request, or return the identity of the request already in flight.
   * Coalescing prevents mount/log/timer callers from continually invalidating
   * one another while a slower disk-backed server handler is still running.
   */
  request(event: HydrationEvent, payload: HydrationPayload): string | undefined {
    const key = hydrationKey(event, payload)
    const existing = this.pending.get(key)
    if (existing) {
      // A refresh reason arrived while this resource was in flight. Keep the
      // single flight, but remember to issue one fresh read after its response
      // commits so a burst cannot leave the UI on the pre-burst snapshot.
      existing.dirty = true
      return existing.requestId
    }

    const request: PendingRequest = {
      event,
      payload,
      requestId: this.metadataSupported ? `e${this.epoch}-${++this.sequence}` : undefined,
      epoch: this.epoch,
      attempts: 0,
      dirty: false,
    }
    this.pending.set(key, request)
    this.dispatch(key, request)
    return request.requestId
  }

  /**
   * Accept only the response for this connection/request.  Legacy responses
   * have no metadata and remain valid while capability negotiation is absent.
   */
  accept(event: HydrationEvent, payload: ResponseMeta & Record<string, unknown>): boolean {
    if (payload.server_instance_id && this.serverInstanceId && payload.server_instance_id !== this.serverInstanceId) {
      return false
    }

    const key = responseHydrationKey(event, payload)
    const request = this.pending.get(key)
    if (request && request.epoch !== this.epoch) return false

    if (request?.requestId) {
      if (payload.request_id !== request.requestId) return false
    } else if (!request && this.metadataSupported) {
      // Once negotiation is complete, an uncorrelated response with no
      // in-flight request can only be delayed traffic from an earlier epoch.
      return false
    }

    if (request) {
      if (request.timer) clearTimeout(request.timer)
      this.pending.delete(key)
      if (request.dirty) this.request(request.event, request.payload)
    }
    return true
  }

  hasPending(event: HydrationEvent, payload: HydrationPayload): boolean {
    return this.pending.has(hydrationKey(event, payload))
  }

  dispose(): void {
    for (const request of this.pending.values()) {
      if (request.timer) clearTimeout(request.timer)
    }
    this.pending.clear()
  }

  private dispatch(key: string, request: PendingRequest): void {
    request.attempts += 1
    const basePayload = request.payload && typeof request.payload === 'object' ? request.payload : undefined
    const payload = request.requestId ? { ...basePayload, request_id: request.requestId } : basePayload
    const legacyArity = CLIENT_EVENT_ARITY[request.event]

    // Before advertisement, preserve the historical packet arity exactly.
    // Once advertised, all hydration handlers accept one metadata object.
    const arity: 0 | 1 = this.metadataSupported ? 1 : legacyArity
    this.wireEmit(request.event, payload, arity)

    request.timer = setTimeout(() => {
      if (this.pending.get(key) !== request || request.epoch !== this.epoch) return
      if (request.attempts < this.maxAttempts) {
        this.dispatch(key, request)
      } else {
        this.pending.delete(key)
      }
    }, this.retryMs)
  }
}
