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
  /** In-process restore trust, separate from startup handoff recovery. */
  restoreRecoveryRequired: boolean
  restorePending: boolean
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
  setStatus: (status: ServerEvents['status_update']) => void
  setRestoreResult: (result: ServerEvents['restore_complete']) => void
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
  restoreRecoveryRequired: false,
  restorePending: false,
  version: null,
  snapshotRevision: -1,
  serverInstanceId: null,

  beginConnection: () => set({ serverInstanceId: null, snapshotRevision: -1 }),
  // Transport loss must not erase whether a game was running. The derived UI
  // mode still becomes disconnected and locks input until transport returns.
  setConnected: (connected) => set(connected ? { connected } : { connected, inputAuthorized: false, startupInputReady: false }),
  startRequested: () => set({ mode: 'starting', inputAuthorized: false, startupInputReady: false }),
  gameStarted: (message) => set({ mode: 'play', statusMessage: message, inputAuthorized: true, startupInputReady: false }),
  gameResumed: (isProcessing) => set({ mode: 'play', isProcessing, inputAuthorized: true, startupInputReady: false }),
  setWelcome: (message) => set({ welcomeMessage: message }),
  setStatus: (status) =>
    set((s) => ({
      statusMessage: status.message,
      isProcessing: status.is_processing,
      restoreRecoveryRequired: status.recovery_required ?? s.restoreRecoveryRequired,
      startupInputReady: s.mode === 'starting' && s.startupStatus === 'in_progress' && !status.is_processing
        ? true
        : s.startupInputReady,
    })),
  setStartup: (status, phase, startupAttemptId) => set((s) => ({
    startupStatus: status,
    startupPhase: phase,
    startupAttemptId: startupAttemptId ?? s.startupAttemptId,
    inputAuthorized: status === 'in_progress' ? true : status === 'failed' ? false : s.inputAuthorized,
    startupInputReady: status === 'in_progress' ? false : s.startupInputReady,
  })),
  setRecovery: (recovery) => set({ recovery }),
  setRestoreResult: (result) => set((s) => ({
    restorePending: result.pending === true,
    restoreRecoveryRequired: result.can_resume === false || result.restore_outcome === 'recovery_required',
    statusMessage: result.message,
    inputAuthorized: result.restart_required === false && result.can_resume !== false ? s.inputAuthorized : false,
    startupInputReady: result.restart_required === false && result.can_resume !== false ? s.startupInputReady : false,
  })),
  setVersion: (version) => set({ version }),
  applySnapshot: (snapshot) =>
    set((s) => {
      if (!shouldAcceptSnapshot(s, snapshot)) return {}
      return {
        serverInstanceId: snapshot.server_instance_id,
        snapshotRevision: snapshot.revision,
        mode: snapshot.game_running ? 'play' : 'disconnected',
        isProcessing: snapshot.is_processing,
        statusMessage: snapshot.status_message,
        restorePending: snapshot.operations?.restore?.pending === true,
        restoreRecoveryRequired: snapshot.operations?.restore?.can_resume === false
          || snapshot.operations?.restore?.restore_outcome === 'recovery_required',
        startupStatus: snapshot.startup?.status ?? s.startupStatus,
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
