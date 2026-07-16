import { create } from 'zustand'
import type { GameMessage, ServerEvents } from '../contract/events'

const MESSAGE_RING_LIMIT = 500
const DEBUG_RING_LIMIT = 200

export interface GeneratedImage {
  image_url: string
  prompt: string
}

export interface LogState {
  /** Game log ring (game_output / cached_messages). */
  messages: GameMessage[]
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
  clear: () => void
}

export const useLog = create<LogState>((set) => ({
  messages: [],
  debug: [],
  tokens: { tpm: 0, rpm: 0, total_tokens: 0 },
  images: [],

  append: (message) =>
    set((s) => ({ messages: [...s.messages, message].slice(-MESSAGE_RING_LIMIT) })),
  replaceAll: (messages) => set({ messages: messages.slice(-MESSAGE_RING_LIMIT) }),
  appendDebug: (message) =>
    set((s) => ({ debug: [...s.debug, message].slice(-DEBUG_RING_LIMIT) })),
  setTokens: (tokens) => set({ tokens }),
  addImage: (image) => set((s) => ({ images: [...s.images, image] })),
  clear: () => set({ messages: [], debug: [] }),
}))
