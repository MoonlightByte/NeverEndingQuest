import { create } from 'zustand'
import type { PlayAllowancePayload } from '../contract/events'

/**
 * #2072: the hosted play allowance, as the server last sent it (memory only, never persisted).
 * `value` is null until a payload arrives and after a disconnect; an `unavailable` payload (a failed
 * read) also shows nothing. A refused line waits in `refused` for the composer, which takes it once.
 */
export const useAllowance = create<{
  value: PlayAllowancePayload | null
  refused: string | null
  receive: (payload: PlayAllowancePayload) => void
  takeRefused: () => string | null
  clear: () => void
}>((set, get) => ({
  value: null,
  refused: null,
  receive: (payload) => {
    const { refused_input: refusedInput, ...value } = payload
    set({ value, ...(typeof refusedInput === 'string' && refusedInput ? { refused: refusedInput } : {}) })
  },
  takeRefused: () => {
    const text = get().refused
    if (text !== null) set({ refused: null })
    return text
  },
  clear: () => set({ value: null, refused: null }),
}))
