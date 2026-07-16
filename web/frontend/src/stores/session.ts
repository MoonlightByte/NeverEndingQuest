import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'

/** UI mode state machine (plan Task 4.5 seeds live here). */
export type UiMode = 'disconnected' | 'starting' | 'play' | 'combat'

export type StartupStatus = 'idle' | 'in_progress' | 'ready' | 'failed'

export interface SessionState {
  /** Socket transport connected. */
  connected: boolean
  /** Coarse UI mode; MODAL overlays are orthogonal (dialogs store). */
  mode: UiMode
  /** Server is processing a turn -- input locked. */
  isProcessing: boolean
  /** Status ticker text (status_update.message). */
  statusMessage: string
  /** Startup lifecycle (startup_status). */
  startupStatus: StartupStatus
  startupPhase: string
  /** Last startup_recovery_response payload. */
  recovery: ServerEvents['startup_recovery_response'] | null
  /** Last version_status payload. */
  version: ServerEvents['version_status'] | null

  setConnected: (connected: boolean) => void
  /** User pressed Start (start_game emitted). */
  startRequested: () => void
  gameStarted: (message: string) => void
  gameResumed: (isProcessing: boolean) => void
  setStatus: (status: { message: string; is_processing: boolean }) => void
  setStartup: (status: 'in_progress' | 'ready' | 'failed', phase: string) => void
  setRecovery: (recovery: ServerEvents['startup_recovery_response']) => void
  setVersion: (version: ServerEvents['version_status']) => void
  /** Driven by initiative_data_response.active: play <-> combat. */
  setCombatActive: (active: boolean) => void
}

export const useSession = create<SessionState>((set) => ({
  connected: false,
  mode: 'disconnected',
  isProcessing: false,
  statusMessage: '',
  startupStatus: 'idle',
  startupPhase: '',
  recovery: null,
  version: null,

  setConnected: (connected) =>
    set((s) => ({ connected, mode: connected ? s.mode : 'disconnected' })),
  startRequested: () => set({ mode: 'starting' }),
  gameStarted: (message) => set({ mode: 'play', statusMessage: message }),
  gameResumed: (isProcessing) => set({ mode: 'play', isProcessing }),
  setStatus: (status) =>
    set({ statusMessage: status.message, isProcessing: status.is_processing }),
  setStartup: (status, phase) => set({ startupStatus: status, startupPhase: phase }),
  setRecovery: (recovery) => set({ recovery }),
  setVersion: (version) => set({ version }),
  setCombatActive: (active) =>
    set((s) => {
      if (active) return { mode: 'combat' as const }
      return s.mode === 'combat' ? { mode: 'play' as const } : {}
    }),
}))
