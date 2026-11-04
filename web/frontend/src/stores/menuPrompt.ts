import { create } from 'zustand'
import type { MenuPrompt } from '../contract/events'

export const useMenuPrompt = create<{
  prompt: MenuPrompt | null
  /** A click is on its way; the log shows the player's line when it lands (#1129). */
  answered: boolean
  setPrompt: (prompt: MenuPrompt | null) => void
  markAnswered: () => void
  takeAnswered: () => boolean
}>((set, get) => ({
  prompt: null,
  answered: false,
  // Only a click the server took keeps the flag: refused, the panel comes back and no line will follow.
  setPrompt: (prompt) => set((state) => ({ prompt, answered: state.answered && prompt?.submitted === true })),
  markAnswered: () => set({ answered: true }),
  takeAnswered: () => {
    const answered = get().answered
    if (answered) set({ answered: false })
    return answered
  },
}))
