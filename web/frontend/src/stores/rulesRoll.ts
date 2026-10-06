import { create } from 'zustand'
import type { RulesRollPrompt } from '../contract/events'

export const useRulesRoll = create<{
  prompt: RulesRollPrompt | null
  quickFaces: number[]
  setPrompt: (prompt: RulesRollPrompt | null) => void
  addQuickFace: (face: number) => void
  clearQuickFaces: () => void
}>((set) => ({
  prompt: null,
  quickFaces: [],
  setPrompt: (prompt) => set((state) => ({
    prompt,
    quickFaces: prompt && prompt.id === state.prompt?.id ? state.quickFaces : [],
  })),
  addQuickFace: (face) => set((state) => state.prompt && !state.prompt.submitted
    && Number.isInteger(face) && face >= 1 && face <= 20
    ? { quickFaces: [...state.quickFaces, face].slice(-state.prompt.faces) } : {}),
  clearQuickFaces: () => set({ quickFaces: [] }),
}))
