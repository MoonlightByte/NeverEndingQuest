import { create } from 'zustand'

/**
 * #1732: a player line the server never acknowledged (the connection dropped,
 * or its transport died unseen). The composer takes it back into the box once,
 * with a note; it is never sent again by itself.
 */
export const useUnsentLine = create<{
  line: string | null
  report: (text: string) => void
  take: () => string | null
}>((set, get) => ({
  line: null,
  report: (text) => set({ line: text }),
  take: () => {
    const text = get().line
    if (text !== null) set({ line: null })
    return text
  },
}))
