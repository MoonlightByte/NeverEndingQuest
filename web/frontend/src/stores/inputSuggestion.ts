import { create } from 'zustand'

/**
 * #882: text the game offers for the composer (the player's declared opening
 * action at their first combat turn). The composer takes it once, and only
 * into an empty draft; it is never a log message.
 */
export const useInputSuggestion = create<{
  suggestion: string | null
  offer: (text: string) => void
  take: () => string | null
}>((set, get) => ({
  suggestion: null,
  offer: (text) => set({ suggestion: text }),
  take: () => {
    const text = get().suggestion
    if (text !== null) set({ suggestion: null })
    return text
  },
}))
