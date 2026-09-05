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
  /** Mirrors legacy gameStarted/startupInputEnabled command authorization. */
  inputAuthorized: boolean
  /** A non-busy status update has opened the startup wizard input prompt. */
  startupInputReady: boolean
  /** Status ticker text (status_update.message). */
  statusMessage: string
  /** #214: background startup-welcome liveness (presentational; never locks input). */
  welcomeMessage: string
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

  beginConnection: () => void
  setConnected: (connected: boolean) => void
  /** User pressed Start (start_game emitted). */
  startRequested: () => void
  gameStarted: (message: string) => void
  gameResumed: (isProcessing: boolean) => void
  setStatus: (status: { message: string; is_processing: boolean }) => void
  setWelcome: (message: string) => void
  setStartup: (status: 'in_progress' | 'ready' | 'failed', phase: string, startupAttemptId?: string) => void
  setRecovery: (recovery: ServerEvents['startup_recovery_response']) => void
  setVersion: (version: ServerEvents['version_status']) => void
  applySnapshot: (snapshot: ServerEvents['ui_state_snapshot']) => void
}

export const useSession = create<SessionState>((set) => ({
  connected: false,
  mode: 'disconnected',
  isProcessing: false,
  inputAuthorized: false,
  startupInputReady: false,
  statusMessage: '',
  welcomeMessage: '',
  startupStatus: 'idle',
  startupPhase: '',
  startupAttemptId: '',
  recovery: null,
  version: null,
  snapshotRevision: -1,
  serverInstanceId: null,

  beginConnection: () => set({ serverInstanceId: null, snapshotRevision: -1 }),
  // Transport loss must not erase whether a game was running. The derived UI
  // mode still becomes disconnected and locks input until transport returns.
  setConnected: (connected) => set(connected ? { connected } : { connected, inputAuthorized: false, startupInputReady: false }),
  startRequested: () => set({ mode: 'starting', inputAuthorized: false, startupInputReady: false }),
  gameStarted: (message) => set({ mode: 'play', startupStatus: 'ready', statusMessage: message, inputAuthorized: true, startupInputReady: false }),
  gameResumed: (isProcessing) => set((s) => ({
    mode: s.startupStatus === 'ready' ? 'play' : 'starting',
    isProcessing,
    inputAuthorized: s.startupStatus === 'ready' || s.startupStatus === 'in_progress',
    startupInputReady: s.startupStatus === 'in_progress' && !isProcessing,
  })),
  setWelcome: (message) => set({ welcomeMessage: message }),
  setStatus: (status) =>
    set((s) => ({
      statusMessage: status.message,
      isProcessing: status.is_processing,
      startupInputReady: s.mode === 'starting' && s.startupStatus === 'in_progress' && !status.is_processing
        ? true
        : s.startupInputReady,
    })),
  setStartup: (status, phase, startupAttemptId) => set((s) => ({
    startupStatus: status,
    startupPhase: phase,
    startupAttemptId: startupAttemptId ?? s.startupAttemptId,
    mode: status === 'ready' ? 'play' : 'starting',
    inputAuthorized: status !== 'failed',
    startupInputReady: false,
  })),
  setRecovery: (recovery) => set({ recovery }),
  setVersion: (version) => set({ version }),
  applySnapshot: (snapshot) =>
    set((s) => {
      if (!shouldAcceptSnapshot(s, snapshot)) return {}
      const startupStatus = snapshot.startup?.status ?? s.startupStatus
      return {
        serverInstanceId: snapshot.server_instance_id,
        snapshotRevision: snapshot.revision,
        mode: snapshot.game_running ? (startupStatus === 'ready' ? 'play' : 'starting') : 'disconnected',
        inputAuthorized: snapshot.game_running && (startupStatus === 'ready' || startupStatus === 'in_progress'),
        startupInputReady: snapshot.game_running && startupStatus === 'in_progress' && !snapshot.is_processing,
        isProcessing: snapshot.is_processing,
        statusMessage: snapshot.status_message,
        startupStatus,
        startupPhase: snapshot.startup?.phase ?? s.startupPhase,
        startupAttemptId: snapshot.startup?.startupAttemptId ?? s.startupAttemptId,
      }
    }),
}))

export function shouldAcceptSnapshot(
  current: Pick<SessionState, 'serverInstanceId' | 'snapshotRevision'>,
  snapshot: ServerEvents['ui_state_snapshot'],
): boolean {
  if (current.serverInstanceId && snapshot.server_instance_id !== current.serverInstanceId) return false
  return snapshot.revision >= current.snapshotRevision
}
