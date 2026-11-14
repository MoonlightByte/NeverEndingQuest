import { create } from 'zustand'

/**
 * #882: text the game offers for the composer (the player's declared opening
 * action at their first combat turn). The composer takes it once, and only
 * into an empty draft; it is never a log message.
 * #1990: `reason` "lost_words" marks the player's own words given back after a
 * turn the game could not carry out (#1968); the composer then says so under
 * the box. `forgotten` counts Load, Reset and new-game signals: the composer
 * drops that hint on each one and leaves the box text alone.
 */
export interface InputSuggestion { text: string; reason?: string }

export const useInputSuggestion = create<{
  suggestion: InputSuggestion | null
  forgotten: number
  offer: (text: string, reason?: string) => void
  take: () => InputSuggestion | null
  forget: () => void
}>((set, get) => ({
  suggestion: null,
  forgotten: 0,
  offer: (text, reason) => set({ suggestion: reason === undefined ? { text } : { text, reason } }),
  take: () => {
    const taken = get().suggestion
    if (taken !== null) set({ suggestion: null })
    return taken
  },
  forget: () => set((s) => ({ suggestion: null, forgotten: s.forgotten + 1 })),
}))
