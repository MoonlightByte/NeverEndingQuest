import { create } from 'zustand'

export const CREATION_CANCELLED = 'Character creation was cancelled. Choose an adventure to start again.'
export function isTransientNotice(content: string): boolean {
  return [CREATION_CANCELLED, 'Disconnected from the game server. Reconnecting...', 'Reconnected to your character setup.', 'Reconnected to your game in progress.'].includes(content)
}
export const useConnectionNotice = create<{ text: string; revision: number; show: (text: string) => void; clear: () => void }>((set) => ({
  text: '', revision: 0,
  show: (text) => set((s) => ({ text, revision: s.revision + 1 })),
  clear: () => set({ text: '' }),
}))
