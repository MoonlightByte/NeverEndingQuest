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
  debug: [],
  tokens: { tpm: 0, rpm: 0, total_tokens: 0 },
  images: [],

  append: (message) =>
    set((s) => {
      if (
        message.message_id &&
        s.messages.some((existing) => existing.message_id === message.message_id)
      ) {
        return {}
      }
      return { messages: [...s.messages, message].slice(-MESSAGE_RING_LIMIT) }
    }),
  // cached_messages can race with newer live output. Merge cached history in
  // front of what is already visible and deduplicate only stable server IDs;
  // replacing the ledger here can erase a turn the player just received.
  replaceAll: (cached) =>
    set((s) => {
      const seen = new Set<string>()
      const merged: Array<{ message: GameMessage; cached: boolean }> = []
      for (const [message, isCached] of [
        ...cached.map((message) => [message, true] as const),
        ...s.messages.map((message) => [message, false] as const),
      ]) {
        if (message.message_id) {
          if (seen.has(message.message_id)) continue
          seen.add(message.message_id)
        }
        merged.push({ message, cached: isCached })
      }
      const trimmed = merged.slice(-MESSAGE_RING_LIMIT)
      const retainedCached = trimmed.filter((entry) => entry.cached).length
      return { messages: trimmed.map((entry) => entry.message), previousSessionCount: retainedCached }
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
  clear: () => set({ messages: [], previousSessionCount: 0, debug: [] }),
}))
