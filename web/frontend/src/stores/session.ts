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
  startupAttemptId: string
  /** Last startup_recovery_response payload. */
  recovery: ServerEvents['startup_recovery_response'] | null
  /** Last version_status payload. */
  version: ServerEvents['version_status'] | null
  snapshotRevision: number
  serverInstanceId: string | null

  setConnected: (connected: boolean) => void
  /** User pressed Start (start_game emitted). */
  startRequested: () => void
  gameStarted: (message: string) => void
  gameResumed: (isProcessing: boolean) => void
  setStatus: (status: { message: string; is_processing: boolean }) => void
  setStartup: (status: 'in_progress' | 'ready' | 'failed', phase: string, startupAttemptId?: string) => void
  setRecovery: (recovery: ServerEvents['startup_recovery_response']) => void
  setVersion: (version: ServerEvents['version_status']) => void
  applySnapshot: (snapshot: ServerEvents['ui_state_snapshot']) => void
}

export const useSession = create<SessionState>((set) => ({
  connected: false,
  mode: 'disconnected',
  isProcessing: false,
  statusMessage: '',
  startupStatus: 'idle',
  startupPhase: '',
  startupAttemptId: '',
  recovery: null,
  version: null,
  snapshotRevision: -1,
  serverInstanceId: null,

  // Transport loss must not erase whether a game was running. The derived UI
  // mode still becomes disconnected and locks input until transport returns.
  setConnected: (connected) => set({ connected }),
  startRequested: () => set({ mode: 'starting' }),
  gameStarted: (message) => set({ mode: 'play', statusMessage: message }),
  gameResumed: (isProcessing) => set({ mode: 'play', isProcessing }),
  setStatus: (status) =>
    set({ statusMessage: status.message, isProcessing: status.is_processing }),
  setStartup: (status, phase, startupAttemptId) => set((s) => ({ startupStatus: status, startupPhase: phase, startupAttemptId: startupAttemptId ?? s.startupAttemptId })),
  setRecovery: (recovery) => set({ recovery }),
  setVersion: (version) => set({ version }),
  applySnapshot: (snapshot) =>
    set((s) => {
      const changed = snapshot.server_instance_id !== s.serverInstanceId
      if (!changed && snapshot.revision < s.snapshotRevision) return {}
      return {
        serverInstanceId: snapshot.server_instance_id,
        snapshotRevision: snapshot.revision,
        mode: snapshot.game_running ? 'play' : 'disconnected',
        isProcessing: snapshot.is_processing,
        statusMessage: snapshot.status_message,
        startupStatus: snapshot.startup?.status ?? s.startupStatus,
        startupPhase: snapshot.startup?.phase ?? s.startupPhase,
        startupAttemptId: snapshot.startup?.startupAttemptId ?? s.startupAttemptId,
      }
    }),
}))
