import { isTransientNotice } from './connectionNotices'
import { create } from 'zustand'
import type { GameMessage, ServerEvents } from '../contract/events'

const MESSAGE_RING_LIMIT = 500
const DEBUG_RING_LIMIT = 200

export interface GeneratedImage {
  image_url: string
  prompt: string
  request_id?: string
  source_message_id?: string
}

export interface LogState {
  /** Game log ring (game_output / cached_messages). */
  messages: GameMessage[]
  /** Number of leading cached messages rendered under Previous Session. */
  previousSessionCount: number
  /** Live output received during the current reconnect history request. */
  historyPending: GameMessage[] | null
  beginHistorySync: () => void
  /** Debug ring (debug_output), shown in the Debug tab. */
  debug: Array<ServerEvents['debug_output']>
  /** Token counters (token_update): TPM / RPM / total. */
  tokens: ServerEvents['token_update']
  /** Inline generated images (image_generated). */
  images: GeneratedImage[]

  append: (message: GameMessage) => void
  replaceAll: (messages: GameMessage[]) => void
  appendDebug: (message: ServerEvents['debug_output']) => void
  setTokens: (tokens: ServerEvents['token_update']) => void
  addImage: (image: GeneratedImage) => void
  imageFailed: (error: ServerEvents['image_generation_error']) => void
  clear: () => void
}

export const useLog = create<LogState>((set) => ({
  messages: [],
  previousSessionCount: 0,
  historyPending: null,
  beginHistorySync: () => set({ historyPending: [] }),
  debug: [],
  tokens: { tpm: 0, rpm: 0, total_tokens: 0 },
  images: [],

  append: (message) =>
    set((s) => {
      if (message.type === 'system' && isTransientNotice(message.content)) return {}
      if (
        message.message_id &&
        s.messages.some((existing) => existing.message_id === message.message_id)
      ) {
        return {}
      }
      const dropped = Math.max(0, s.messages.length + 1 - MESSAGE_RING_LIMIT)
      return {
        messages: [...s.messages, message].slice(-MESSAGE_RING_LIMIT),
        previousSessionCount: Math.max(0, s.previousSessionCount - dropped),
        historyPending: s.historyPending === null ? null : [...s.historyPending, message].slice(-MESSAGE_RING_LIMIT),
      }
    }),
  // Reconnect history is authoritative. Only output received DURING this
  // connection can follow it: retaining the entire old browser log appends
  // expired interview messages after today's scene once the server ring trims.
  replaceAll: (cached) =>
    set((s) => {
      const seen = new Set<string>()
      const merged: Array<{ message: GameMessage; cached: boolean }> = []
      for (const [message, isCached] of [
        ...cached.map((message) => [message, true] as const),
        ...(s.historyPending ?? s.messages).map((message) => [message, false] as const),
      ]) {
        if (message.type === 'system' && isTransientNotice(message.content)) continue
        if (message.message_id) {
          if (seen.has(message.message_id)) continue
          seen.add(message.message_id)
        }
        merged.push({ message, cached: isCached })
      }
      const trimmed = merged.slice(-MESSAGE_RING_LIMIT)
      const retainedCached = trimmed.filter((entry) => entry.cached).length
      return { messages: trimmed.map((entry) => entry.message), previousSessionCount: retainedCached, historyPending: null }
    }),
  appendDebug: (message) =>
    set((s) => ({ debug: [...s.debug, message].slice(-DEBUG_RING_LIMIT) })),
  setTokens: (tokens) => set({ tokens }),
  addImage: (image) => set((s) => image.request_id && s.images.some((entry) => entry.request_id === image.request_id) ? {} : ({ images: [...s.images, image] })),
  imageFailed: (failure) =>
    set((s) => ({
      messages: [...s.messages, {
        type: 'error' as const,
        content: failure.message,
        message_id: failure.request_id ? `image-error-${failure.request_id}` : undefined,
      }].slice(-MESSAGE_RING_LIMIT),
    })),
  clear: () => set({ messages: [], previousSessionCount: 0, historyPending: null, debug: [] }),
}))
